from __future__ import annotations

import json
from typing import Any

from .paddle_adapter import (
    PaddleOCRUnavailableError,
    _configure_paddle_runtime,
    _to_numpy_image,
    select_paddle_device,
)
from ocr_api.settings import get_settings


class PaddleOCRVLAdapter:
    """PaddleOCR-VL-1.6 适配器。

    直接返回 PaddleOCR-VL 的原始 JSON。身份证、营业执照等业务字段由调用方
    根据自身协议进行解析和封装。
    """

    def __init__(self, pipeline_version: str = "v1.6", enable_orientation: bool = True):
        self.pipeline_version = pipeline_version
        self.enable_orientation = enable_orientation
        self._engine: Any | None = None

    def recognize(self, image: Any) -> dict[str, Any] | list[dict[str, Any]]:
        """识别图片，并返回 PaddleOCR-VL 原始 JSON 结果。"""
        engine = self._get_engine()
        prepared_image = _compress_image_if_configured(image, get_settings().ocr_compress_max_side)
        result = engine.predict(input=_to_numpy_image(prepared_image))
        return extract_paddleocr_vl_json(result)

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


def extract_paddleocr_vl_json(result: Any) -> dict[str, Any] | list[dict[str, Any]]:
    """提取 PaddleOCR-VL Result 对象公开的 JSON。

    PaddleOCR-VL 单张图片通常返回一个 Result 对象的列表；多页文档则可能返回多个
    Result。单页保持对象形式，多页保持数组形式，避免 Python 服务擅自改变模型数据。
    """
    payloads: list[dict[str, Any]] = []
    for item in _as_list(result):
        payload = _result_to_json(item)
        if payload is None:
            raise PaddleOCRUnavailableError("PaddleOCR-VL 识别结果无法转换为 JSON。")
        payloads.append(payload)

    if not payloads:
        return {}
    if len(payloads) == 1:
        return payloads[0]
    return payloads


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


def _result_to_json(item: Any) -> dict[str, Any] | None:
    # PaddleOCR-VL 的 Result.json 不包含 input_img 等大对象，应优先使用它。
    for attr in ["json", "to_json", "dict", "to_dict"]:
        if not hasattr(item, attr):
            continue
        value = getattr(item, attr)
        try:
            value = value() if callable(value) else value
        except TypeError:
            continue
        parsed = _parse_json_mapping(value)
        if parsed is not None:
            return parsed

    if isinstance(item, dict):
        # 结果对象有时继承 dict；转成普通 dict，避免把 Paddle 的对象实例透传给 FastAPI。
        return dict(item)

    return None


def _parse_json_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


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


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
