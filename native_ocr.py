from __future__ import annotations

import json
import logging
import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from ocr_settings import get_settings


logger = logging.getLogger(__name__)


class NativeOCRUnavailableError(RuntimeError):
    """原生 PaddleOCR-VL 服务不可用。"""


class NativePaddleOCRVLRecognizer:
    """Windows 原生 Python 版 PaddleOCR-VL 识别器。"""

    def __init__(self, pipeline_version: str = "v1.6", enable_orientation: bool = True):
        self.pipeline_version = pipeline_version
        self.enable_orientation = enable_orientation
        self._engine: Any | None = None

    def recognize(
        self,
        file_bytes: bytes,
        file_type: int,
        *,
        visualize: bool = False,
    ) -> dict[str, Any]:
        del visualize
        if file_type == 0:
            raw_result = self._predict_pdf(file_bytes)
        elif file_type == 1:
            raw_result = self._predict_image(file_bytes)
        else:
            raise NativeOCRUnavailableError("fileType 只支持 0(PDF) 或 1(图片)。")
        return build_layout_parsing_response(extract_paddleocr_vl_json(raw_result))

    def _predict_image(self, file_bytes: bytes) -> Any:
        try:
            from PIL import Image
            import numpy as np
        except Exception as exc:
            raise NativeOCRUnavailableError("缺少图片处理依赖，请安装 pillow 和 numpy。") from exc

        try:
            image = Image.open(BytesIO(file_bytes)).convert("RGB")
        except Exception as exc:
            raise NativeOCRUnavailableError(f"图片读取失败：{_format_exception_chain(exc)}") from exc

        max_side = get_settings().ocr_compress_max_side
        if max_side is not None and max(image.size) > max_side:
            image = image.copy()
            image.thumbnail((max_side, max_side))

        return _predict_with_fallback(self._get_engine(), np.asarray(image))

    def _predict_pdf(self, file_bytes: bytes) -> Any:
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name
            return _predict_with_fallback(self._get_engine(), temp_path)
        finally:
            if temp_path is not None:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    logger.warning("临时 PDF 文件删除失败：%s", temp_path)

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine

        _configure_paddle_runtime()
        try:
            from paddleocr import PaddleOCRVL
        except Exception as exc:
            raise NativeOCRUnavailableError("未安装 PaddleOCR-VL，请安装 paddleocr 和 paddlepaddle-gpu。") from exc

        try:
            self._engine = PaddleOCRVL(
                pipeline_version=self.pipeline_version,
                device=_select_paddle_device(),
                use_doc_orientation_classify=self.enable_orientation,
                use_doc_unwarping=False,
                use_layout_detection=True,
                use_chart_recognition=False,
                use_seal_recognition=False,
                use_ocr_for_image_block=False,
                use_queues=False,
            )
        except Exception as exc:
            raise NativeOCRUnavailableError(f"PaddleOCR-VL 初始化失败：{_format_exception_chain(exc)}") from exc
        return self._engine


def build_layout_parsing_response(raw_json: Any) -> dict[str, Any]:
    """包装为官方 layout-parsing 风格响应，便于本地和 Docker 服务切换。"""
    return {
        "result": {
            "layoutParsingResults": [
                {"prunedResult": item} for item in _as_list(raw_json)
            ]
        }
    }


def extract_paddleocr_vl_json(result: Any) -> dict[str, Any] | list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for item in _as_list(result):
        payload = _result_to_json(item)
        if payload is None:
            raise NativeOCRUnavailableError("PaddleOCR-VL 识别结果无法转换为 JSON。")
        payloads.append(payload)

    if not payloads:
        return {}
    if len(payloads) == 1:
        return payloads[0]
    return payloads


def _configure_paddle_runtime() -> None:
    settings = get_settings()
    os.environ.setdefault("FLAGS_enable_pir_api", "0")
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("FLAGS_use_onednn", "0")
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", settings.model_cache_dir)
    try:
        import paddle

        if not paddle.in_dynamic_mode():
            paddle.disable_static()
    except Exception:
        pass


def _select_paddle_device() -> str:
    configured_device = get_settings().ocr_device
    if configured_device:
        return configured_device
    try:
        import paddle

        if paddle.device.cuda.device_count() > 0:
            return "gpu:0"
    except Exception:
        pass
    return "cpu"


def _predict_with_fallback(engine: Any, input_value: Any) -> Any:
    try:
        return _predict_with_safe_document_options(engine, input_value)
    except AssertionError as exc:
        logger.warning(
            "PaddleOCR-VL 版面解析触发断言，改用整图 OCR 模式重试：%s",
            _format_exception_chain(exc),
        )
        try:
            return _predict_with_whole_image_ocr_options(engine, input_value)
        except Exception as retry_exc:
            raise NativeOCRUnavailableError(
                f"PaddleOCR-VL 推理失败：{_format_exception_chain(retry_exc)}"
            ) from retry_exc
    except Exception as exc:
        raise NativeOCRUnavailableError(f"PaddleOCR-VL 推理失败：{_format_exception_chain(exc)}") from exc


def _predict_with_safe_document_options(engine: Any, input_value: Any) -> Any:
    return engine.predict(
        input=input_value,
        use_seal_recognition=False,
        use_ocr_for_image_block=False,
    )


def _predict_with_whole_image_ocr_options(engine: Any, input_value: Any) -> Any:
    return engine.predict(
        input=input_value,
        use_layout_detection=False,
        prompt_label="ocr",
        use_seal_recognition=False,
        use_ocr_for_image_block=False,
        layout_shape_mode="rect",
    )


def _result_to_json(item: Any) -> dict[str, Any] | None:
    official_json_error: BaseException | None = None
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
            return _safe_json_value(parsed)

    if isinstance(item, dict):
        if official_json_error is not None:
            logger.warning(
                "PaddleOCR-VL 官方 JSON 导出失败，改用兼容导出：%s",
                _format_exception_chain(official_json_error),
            )
        return _safe_json_value(dict(item))
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


_SKIPPED_JSON_KEYS = {"input_img", "output_img", "imgs_in_doc", "image", "images", "img"}


def _safe_json_value(value: Any, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth >= 8:
        return _summarize_value(value)
    if isinstance(value, dict):
        return {
            str(key): _safe_json_value(item, depth + 1)
            for key, item in value.items()
            if str(key) not in _SKIPPED_JSON_KEYS
        }
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
