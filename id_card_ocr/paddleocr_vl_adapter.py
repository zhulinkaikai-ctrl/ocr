from __future__ import annotations

import json
from typing import Any

from .models import OCRLine
from .paddle_adapter import (
    PaddleOCRUnavailableError,
    _configure_paddle_runtime,
    _to_numpy_image,
    normalize_paddle_result,
    select_paddle_device,
)
from ocr_api.settings import get_settings


class PaddleOCRVLAdapter:
    """PaddleOCR-VL-1.6 适配器。

    外部接口仍然返回 OCRLine 列表，让身份证、营业执照等业务提取器不用关心 VL
    文档解析模型的原始结果结构。
    """

    def __init__(self, pipeline_version: str = "v1.6", enable_orientation: bool = True):
        self.pipeline_version = pipeline_version
        self.enable_orientation = enable_orientation
        self._engine: Any | None = None

    def recognize(self, image: Any) -> list[OCRLine]:
        """识别图片，并把 VL 结果压平成业务提取器可消费的 OCRLine。"""
        engine = self._get_engine()
        prepared_image = _compress_image_if_configured(image, get_settings().ocr_compress_max_side)
        result = engine.predict(input=_to_numpy_image(prepared_image))
        return normalize_paddleocr_vl_result(result)

    def _get_engine(self) -> Any:
        """延迟初始化 PaddleOCR-VL，避免 API 启动时立刻加载大模型。"""
        if self._engine is not None:
            return self._engine

        _configure_paddle_runtime()

        try:
            from paddleocr import PaddleOCRVL
        except Exception as exc:
            raise PaddleOCRUnavailableError(
                "未安装 PaddleOCR-VL，请确认 paddleocr 和 paddlepaddle-gpu 已安装。"
            ) from exc

        try:
            self._engine = PaddleOCRVL(
                pipeline_version=self.pipeline_version,
                device=select_paddle_device(),
                use_doc_orientation_classify=self.enable_orientation,
                use_doc_unwarping=False,
                use_layout_detection=True,
                use_chart_recognition=False,
                use_seal_recognition=True,
                use_ocr_for_image_block=True,
                use_queues=False,
            )
        except Exception as exc:
            raise PaddleOCRUnavailableError(
                f"PaddleOCR-VL 初始化失败：{_format_exception_chain(exc)}"
            ) from exc

        return self._engine


def normalize_paddleocr_vl_result(result: Any) -> list[OCRLine]:
    """把 PaddleOCR-VL 的文档解析结果转换为 OCRLine。

    PaddleOCR-VL 的返回对象可能是 Result 对象、dict 或列表。这里先复用普通 OCR
    的归一化逻辑；如果拿不到文本，再解析 VL 常见的 json/markdown 字段。
    """
    lines = normalize_paddle_result(result)
    if lines:
        return lines

    texts: list[str] = []
    for item in _as_list(result):
        data = _result_to_mapping(item)
        if not data:
            continue
        texts.extend(_extract_texts_from_vl_mapping(data))

    return [OCRLine(text=text, confidence=None) for text in _dedupe_texts(texts)]


def _compress_image_if_configured(image: Any, max_side: int | None) -> Any:
    """本地测试可通过环境变量压缩图片；正式环境不配置时保持原图。"""
    if max_side is None or not hasattr(image, "size") or not hasattr(image, "copy"):
        return image

    width, height = image.size
    if max(width, height) <= max_side:
        return image

    resized = image.copy()
    resized.thumbnail((max_side, max_side))
    return resized


def _extract_texts_from_vl_mapping(data: dict[str, Any]) -> list[str]:
    texts: list[str] = []

    payload = data.get("res", data)
    json_payload = payload.get("json")
    if json_payload:
        texts.extend(_extract_json_texts(json_payload))

    markdown_payload = payload.get("markdown")
    if markdown_payload:
        texts.extend(_extract_markdown_texts(markdown_payload))

    texts.extend(_extract_json_texts(payload))
    return texts


def _extract_json_texts(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, dict):
        for key in ["block_content", "text", "content", "ocr_text", "rec_text"]:
            text = value.get(key)
            if isinstance(text, str):
                texts.append(text)
        for key in [
            "parsing_res_list",
            "rec_texts",
            "texts",
            "pages",
            "layoutParsingResults",
            "prunedResult",
            "markdown",
            "markdown_texts",
        ]:
            texts.extend(_extract_json_texts(value.get(key)))
        return texts
    if isinstance(value, (list, tuple)):
        for item in value:
            texts.extend(_extract_json_texts(item))
        return texts
    if isinstance(value, str):
        # 某些结果对象会把嵌套 JSON 作为字符串返回，先尝试还原结构，
        # 普通 OCR 文本解析失败后仍按原文保留。
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                return _extract_json_texts(parsed)
        texts.append(value)
    return texts


def _extract_markdown_texts(value: Any) -> list[str]:
    if isinstance(value, dict):
        return _extract_json_texts(value.get("markdown_texts") or value.get("text") or value)
    if isinstance(value, list):
        return _extract_json_texts(value)
    if isinstance(value, str):
        return [value]
    return []


def _result_to_mapping(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item

    for attr in ["json", "to_json", "dict", "to_dict"]:
        if not hasattr(item, attr):
            continue
        value = getattr(item, attr)
        try:
            value = value() if callable(value) else value
        except TypeError:
            continue
        mapping = _parse_mapping(value)
        if mapping:
            return mapping

    # PaddleOCR-VL 某些版本只暴露 markdown 属性，json 属性可能为空或不存在。
    if hasattr(item, "markdown"):
        return {"markdown": getattr(item, "markdown")}

    return {}


def _parse_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _format_exception_chain(exc: BaseException) -> str:
    messages: list[str] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current).strip()
        if message and message not in messages:
            messages.append(message)
        current = current.__cause__ or current.__context__
    return "；".join(messages) if messages else exc.__class__.__name__


def _dedupe_texts(texts: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for text in texts:
        normalized = text.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
