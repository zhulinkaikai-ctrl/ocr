from __future__ import annotations

import json
import logging
from typing import Any

from .paddle_adapter import (
    PaddleOCRUnavailableError,
    _configure_paddle_runtime,
    _to_numpy_image,
    ensure_paddle_dynamic_mode,
    select_paddle_device,
)
from ocr_api.settings import get_settings


logger = logging.getLogger(__name__)


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
        ensure_paddle_dynamic_mode()
        try:
            result = engine.predict(input=_to_numpy_image(prepared_image))
        except Exception as exc:
            raise PaddleOCRUnavailableError(
                f"PaddleOCR-VL 推理失败：{_format_exception_chain(exc)}"
            ) from exc

        ensure_paddle_dynamic_mode()
        try:
            return extract_paddleocr_vl_json(result)
        except PaddleOCRUnavailableError:
            raise
        except Exception as exc:
            raise PaddleOCRUnavailableError(
                f"PaddleOCR-VL 结果转换失败：{_format_exception_chain(exc)}"
            ) from exc

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
    official_json_error: BaseException | None = None

    # PaddleOCR-VL 的 Result.json 不包含 input_img 等大对象，应优先使用它。
    for attr in ["json", "to_json", "dict", "to_dict"]:
        try:
            value = getattr(item, attr)
        except AttributeError:
            continue
        except Exception as exc:
            official_json_error = exc
            continue

        try:
            value = value() if callable(value) else value
        except TypeError:
            continue
        except Exception as exc:
            official_json_error = exc
            continue

        parsed = _parse_json_mapping(value)
        if parsed is not None:
            return parsed

    if isinstance(item, dict):
        if official_json_error is not None:
            logger.warning(
                "PaddleOCR-VL 官方 JSON 导出失败，改用兼容导出：%s",
                _format_exception_chain(official_json_error),
            )
        return _build_paddleocr_vl_json_from_mapping(item)

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


_PADDLEOCR_VL_JSON_KEYS = [
    "input_path",
    "page_index",
    "page_count",
    "width",
    "height",
    "model_settings",
    "parsing_res_list",
    "spotting_res",
    "doc_preprocessor_res",
    "layout_det_res",
]
_SKIPPED_JSON_KEYS = {"input_img", "output_img", "imgs_in_doc", "image", "images", "img"}
_DEFAULT_SKIP_ORDER_LABELS = {
    "figure_title",
    "vision_footnote",
    "image",
    "chart",
    "table",
    "header",
    "header_image",
    "footer",
    "footer_image",
    "footnote",
    "aside_text",
}


def _build_paddleocr_vl_json_from_mapping(item: dict[str, Any]) -> dict[str, Any]:
    """按 PaddleOCR-VL 官方 JSON 结构，从结果对象 dict 内容做兼容导出。"""
    if "res" in item:
        return _safe_json_value(dict(item))

    if "parsing_res_list" not in item:
        return _safe_json_value(dict(item))

    data: dict[str, Any] = {}
    for key in _PADDLEOCR_VL_JSON_KEYS:
        if key not in item:
            continue
        value = item[key]
        if key == "parsing_res_list":
            data[key] = _format_parsing_blocks(
                value,
                skip_order_labels=getattr(item, "skip_order_labels", None),
            )
        elif key in {"doc_preprocessor_res", "layout_det_res"}:
            data[key] = _nested_result_to_json_value(value)
        elif key == "spotting_res" and not value:
            continue
        else:
            data[key] = _safe_json_value(value)

    return {"res": data}


def _format_parsing_blocks(
    blocks: Any,
    skip_order_labels: Any = None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    order_index = 1
    skip_labels = set(skip_order_labels or _DEFAULT_SKIP_ORDER_LABELS)

    for index, block in enumerate(_as_list(blocks)):
        if isinstance(block, dict):
            result.append(_safe_json_value(block))
            continue

        label = _safe_json_value(getattr(block, "label", ""))
        if label not in skip_labels:
            order = order_index
            order_index += 1
        else:
            order = None

        group_id = getattr(block, "group_id", None)
        block_json = {
            "block_label": label,
            "block_content": _safe_json_value(getattr(block, "content", "")),
            "block_bbox": _safe_json_value(getattr(block, "bbox", [])),
            "block_id": index,
            "block_order": order,
            "group_id": _safe_json_value(group_id if group_id is not None else index),
        }

        for attr in ["global_block_id", "global_group_id", "polygon_points"]:
            value = getattr(block, attr, None)
            if value is not None:
                key = "block_polygon_points" if attr == "polygon_points" else attr
                block_json[key] = _safe_json_value(value)

        result.append(block_json)

    return result


def _nested_result_to_json_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_nested_result_to_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_nested_result_to_json_value(item) for item in value]
    if isinstance(value, dict):
        payload = _result_to_json(value)
        if isinstance(payload, dict) and set(payload.keys()) == {"res"}:
            return payload["res"]
        return payload
    return _safe_json_value(value)


def _safe_json_value(value: Any, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth >= 8:
        return _summarize_value(value)
    if isinstance(value, dict):
        data: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in _SKIPPED_JSON_KEYS:
                continue
            data[key_text] = _safe_json_value(item, depth + 1)
        return data
    if isinstance(value, (list, tuple)):
        return [_safe_json_value(item, depth + 1) for item in value]

    tensor_value = _tensor_to_plain_value(value)
    if tensor_value is not None:
        return _safe_json_value(tensor_value, depth + 1)

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return _summarize_value(value)


def _tensor_to_plain_value(value: Any) -> Any | None:
    for method_name in ["numpy", "tolist"]:
        method = getattr(value, method_name, None)
        if method is None:
            continue
        try:
            plain_value = method()
        except Exception:
            continue
        if hasattr(plain_value, "tolist"):
            try:
                return plain_value.tolist()
            except Exception:
                return plain_value
        return plain_value
    return None


def _summarize_value(value: Any) -> str:
    shape = getattr(value, "shape", None)
    if shape is not None:
        return f"[{value.__class__.__name__} shape={_safe_json_value(shape, depth=8)}]"
    return f"[{value.__class__.__name__}]"


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
