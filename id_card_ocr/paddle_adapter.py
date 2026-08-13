from __future__ import annotations

import json
import os
import inspect
from pathlib import Path
from typing import Any

from .models import OCRLine


class PaddleOCRUnavailableError(RuntimeError):
    """Raised when PaddleOCR is not installed or cannot be initialized."""


class PaddleOCRAdapter:
    def __init__(self, lang: str = "ch", enable_orientation: bool = True):
        self.lang = lang
        self.enable_orientation = enable_orientation
        self._engine: Any | None = None

    def recognize(self, image: Any) -> list[OCRLine]:
        engine = self._get_engine()
        np_image = _to_numpy_image(image)

        if hasattr(engine, "predict"):
            try:
                result = engine.predict(np_image)
            except TypeError:
                result = engine.predict(input=np_image)
            return normalize_paddle_result(result)

        if hasattr(engine, "ocr"):
            ocr_kwargs = {}
            if _ocr_accepts_cls(engine.ocr):
                ocr_kwargs["cls"] = self.enable_orientation
            result = engine.ocr(np_image, **ocr_kwargs)
            return normalize_paddle_result(result)

        raise PaddleOCRUnavailableError(
            "The current PaddleOCR instance does not support predict or ocr."
        )

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine

        _configure_paddle_runtime()

        try:
            from paddleocr import PaddleOCR
        except Exception as exc:
            raise PaddleOCRUnavailableError(
                "PaddleOCR is not installed. Install paddleocr and paddlepaddle first."
            ) from exc

        init_attempts = [
            {
                "lang": self.lang,
                "device": select_paddle_device(),
                "enable_mkldnn": False,
                "use_doc_orientation_classify": self.enable_orientation,
                "use_doc_unwarping": False,
                "use_textline_orientation": self.enable_orientation,
            },
            {
                "lang": self.lang,
                "device": select_paddle_device(),
                "enable_mkldnn": False,
                "use_angle_cls": self.enable_orientation,
            },
            {
                "lang": self.lang,
                "device": select_paddle_device(),
                "enable_mkldnn": False,
            },
        ]

        errors: list[str] = []
        for kwargs in init_attempts:
            try:
                self._engine = PaddleOCR(**kwargs)
                return self._engine
            except TypeError as exc:
                errors.append(str(exc))
                continue
            except Exception as exc:
                raise PaddleOCRUnavailableError(f"PaddleOCR initialization failed: {exc}") from exc

        raise PaddleOCRUnavailableError("PaddleOCR initialization parameters are incompatible: " + " | ".join(errors))


def _configure_paddle_runtime() -> None:
    cache_home = Path(__file__).resolve().parents[1] / ".paddlex_cache"
    cache_home.mkdir(parents=True, exist_ok=True)
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_home)
    os.environ["FLAGS_enable_pir_api"] = "0"
    os.environ["FLAGS_use_onednn"] = "0"
    os.environ["FLAGS_use_mkldnn"] = "0"


def select_paddle_device(paddle_module: Any | None = None) -> str:
    if paddle_module is None:
        try:
            import paddle as paddle_module  # type: ignore[no-redef]
        except Exception:
            return "cpu"

    try:
        if paddle_module.is_compiled_with_cuda():
            return "gpu:0"
    except Exception:
        return "cpu"
    return "cpu"


def _ocr_accepts_cls(method: Any) -> bool:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return False
    return "cls" in signature.parameters


def normalize_paddle_result(result: Any) -> list[OCRLine]:
    lines = _normalize_v3_result(result)
    if lines:
        return lines
    return _normalize_v2_result(result)


def _normalize_v3_result(result: Any) -> list[OCRLine]:
    lines: list[OCRLine] = []
    for item in _as_list(result):
        data = _result_to_mapping(item)
        if not data:
            continue

        payload = data.get("res", data)
        texts = _as_list(payload.get("rec_texts"))
        scores = _as_list(payload.get("rec_scores"))
        boxes = _as_list(_first_present(payload, ["rec_boxes", "rec_polys", "dt_polys"]))

        for index, text in enumerate(texts):
            if text is None or str(text).strip() == "":
                continue
            score = scores[index] if index < len(scores) else None
            box = boxes[index] if index < len(boxes) else None
            lines.append(OCRLine(text=str(text), confidence=_to_float(score), box=_plain_value(box)))
    return lines


def _normalize_v2_result(result: Any) -> list[OCRLine]:
    lines: list[OCRLine] = []

    def visit(node: Any) -> None:
        if not isinstance(node, (list, tuple)):
            return

        if _looks_like_v2_line(node):
            box = node[0]
            text, score = node[1][0], node[1][1]
            if str(text).strip():
                lines.append(OCRLine(text=str(text), confidence=_to_float(score), box=_plain_value(box)))
            return

        for child in node:
            visit(child)

    visit(result)
    return lines


def _looks_like_v2_line(node: Any) -> bool:
    if not isinstance(node, (list, tuple)) or len(node) < 2:
        return False
    rec = node[1]
    return isinstance(rec, (list, tuple)) and len(rec) >= 2 and isinstance(rec[0], str)


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

    return _parse_mapping(item)


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


def _first_present(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _to_numpy_image(image: Any) -> Any:
    try:
        import numpy as np
    except Exception as exc:
        raise PaddleOCRUnavailableError("numpy is required to convert images for PaddleOCR.") from exc

    if hasattr(image, "convert"):
        return np.array(image.convert("RGB"))
    return image


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _plain_value(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value
