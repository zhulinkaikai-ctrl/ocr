from __future__ import annotations

import json
import os
import inspect
from pathlib import Path
from typing import Any

from .models import OCRLine


class PaddleOCRUnavailableError(RuntimeError):
    """PaddleOCR 未安装、初始化失败或当前版本接口不兼容。"""


class PaddleOCRAdapter:
    """屏蔽不同 PaddleOCR 版本差异，并统一输出 OCRLine 列表。

    PaddleOCR 2.x 常用 engine.ocr()，3.x 常用 engine.predict()，
    业务层不需要知道当前安装的是哪一套接口。
    """

    def __init__(self, lang: str = "ch", enable_orientation: bool = True):
        self.lang = lang
        self.enable_orientation = enable_orientation
        self._engine: Any | None = None

    def recognize(self, image: Any) -> list[OCRLine]:
        """识别一张图片，返回统一的文本、置信度和文本框数据。"""
        engine = self._get_engine()
        # PaddleOCR 接受 NumPy 数组；页面/API 传进来的通常是 Pillow Image。
        np_image = _to_numpy_image(image)

        # PaddleOCR 3.x 优先使用 predict。
        if hasattr(engine, "predict"):
            try:
                result = engine.predict(np_image)
            except TypeError:
                result = engine.predict(input=np_image)
            return normalize_paddle_result(result)

        # PaddleOCR 2.x 的兼容分支。有些小版本已经移除了 cls 参数，
        # 所以先检查方法签名再决定是否传入。
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
        """延迟初始化模型，并缓存到当前适配器对象中。"""
        if self._engine is not None:
            return self._engine

        # 环境变量必须在导入/初始化 PaddleOCR 之前设置才会生效。
        _configure_paddle_runtime()

        try:
            from paddleocr import PaddleOCR
        except Exception as exc:
            raise PaddleOCRUnavailableError(
                "PaddleOCR is not installed. Install paddleocr and paddlepaddle first."
            ) from exc

        # PaddleOCR 不同版本接受的初始化参数不同，从新接口到旧接口逐级尝试。
        # TypeError 通常表示“参数名不支持”，可以继续尝试下一组参数；
        # 其他异常多为模型/运行时故障，应直接报告。
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
    """配置模型缓存路径，并规避当前 Windows 环境下的 oneDNN/PIR 属性转换错误。"""
    cache_home = Path(__file__).resolve().parents[1] / ".paddlex_cache"
    cache_home.mkdir(parents=True, exist_ok=True)
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_home)
    os.environ["FLAGS_enable_pir_api"] = "0"
    os.environ["FLAGS_use_onednn"] = "0"
    os.environ["FLAGS_use_mkldnn"] = "0"


def select_paddle_device(paddle_module: Any | None = None) -> str:
    """安装的是 CUDA 版 Paddle 时使用第一张 GPU，否则回退到 CPU。"""
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
    """把 PaddleOCR 2.x/3.x 的不同返回结构转换成统一 OCRLine。"""
    # 先按 3.x 结构解析；没有拿到文本时再尝试 2.x 嵌套列表结构。
    lines = _normalize_v3_result(result)
    if lines:
        return lines
    return _normalize_v2_result(result)


def _normalize_v3_result(result: Any) -> list[OCRLine]:
    """解析 3.x 的 rec_texts/rec_scores/rec_boxes 数组。"""
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
    """递归解析 2.x 常见的 [文本框, (文字, 置信度)] 嵌套结构。"""
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
    # PaddleOCR 3.x 不同补丁版本可能返回 dict、结果对象或 JSON 字符串。
    # 这里依次尝试常见转换方法，统一得到字典。
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
