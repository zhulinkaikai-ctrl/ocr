from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .settings import get_settings


class PPStructureV3UnavailableError(RuntimeError):
    """PP-StructureV3 未安装或无法初始化。"""


class PPStructureV3Adapter:
    """懒加载的 PP-StructureV3 封装器，返回 PaddleX 原始 JSON 结果。"""

    def __init__(
        self,
        lang: str = "ch",
        enable_orientation: bool = True,
        text_detection_model_name: str | None = None,
        text_recognition_model_name: str | None = None,
    ):
        settings = get_settings()
        self.lang = lang
        self.enable_orientation = enable_orientation
        self.text_detection_model_name = text_detection_model_name or settings.ocr_detection_model
        self.text_recognition_model_name = text_recognition_model_name or settings.ocr_recognition_model
        self.cpu_threads = settings.ocr_cpu_threads
        self._engine: Any | None = None

    def recognize(self, input_path: str | Path, **predict_options: Any) -> list[dict[str, Any]]:
        engine = self._get_engine()
        result = engine.predict(str(input_path), **predict_options)
        return [_result_to_json_safe(item) for item in _as_list(result)]

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine

        _configure_paddle_runtime()

        try:
            from paddleocr import PPStructureV3
        except Exception as exc:
            raise PPStructureV3UnavailableError(
                "未安装 PP-StructureV3，请先安装 paddleocr、paddlex 和 paddlepaddle。"
            ) from exc

        try:
            pipeline_options = {
                "device": select_paddle_device(),
                "cpu_threads": self.cpu_threads,
                "enable_mkldnn": False,
                "text_detection_model_name": self.text_detection_model_name,
                "text_recognition_model_name": self.text_recognition_model_name,
                "use_doc_orientation_classify": self.enable_orientation,
                "use_doc_unwarping": False,
                "use_textline_orientation": self.enable_orientation,
                "use_table_recognition": True,
                "use_formula_recognition": False,
                "use_chart_recognition": False,
                "use_seal_recognition": False,
                "use_region_detection": True,
            }
            if not self.text_detection_model_name and not self.text_recognition_model_name:
                pipeline_options["lang"] = self.lang
            self._engine = PPStructureV3(**pipeline_options)
        except Exception as exc:
            raise PPStructureV3UnavailableError(f"PP-StructureV3 初始化失败：{exc}") from exc
        return self._engine


def _configure_paddle_runtime() -> None:
    cache_home = get_settings().model_cache_dir
    cache_home.mkdir(parents=True, exist_ok=True)
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_home)
    os.environ["FLAGS_enable_pir_api"] = "0"
    os.environ["FLAGS_use_onednn"] = "0"
    os.environ["FLAGS_use_mkldnn"] = "0"


def select_paddle_device(paddle_module: Any | None = None) -> str:
    configured_device = get_settings().ocr_device
    if configured_device:
        return configured_device

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


def _result_to_json_safe(result: Any) -> dict[str, Any]:
    value = _extract_result_mapping(result)
    safe_value = _json_safe(value)
    if isinstance(safe_value, dict):
        return safe_value
    return {"res": safe_value}


def _extract_result_mapping(result: Any) -> Any:
    for attr in ("json", "to_json", "to_dict", "dict"):
        if not hasattr(result, attr):
            continue
        value = getattr(result, attr)
        try:
            value = value() if callable(value) else value
        except TypeError:
            continue
        parsed = _parse_json_value(value)
        if parsed is not None:
            return parsed

    parsed = _parse_json_value(result)
    return result if parsed is None else parsed


def _parse_json_value(value: Any) -> Any | None:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Path):
        return value.as_posix()
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
