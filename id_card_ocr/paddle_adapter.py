from __future__ import annotations

import os
from typing import Any

from ocr_api.settings import get_settings


class PaddleOCRUnavailableError(RuntimeError):
    """PaddleOCR 未安装、初始化失败或当前版本接口不兼容。"""


def _configure_paddle_runtime() -> None:
    """配置模型缓存路径，并规避当前 Windows 环境下的 oneDNN/PIR 属性转换错误。"""
    cache_home = get_settings().model_cache_dir
    cache_home.mkdir(parents=True, exist_ok=True)
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_home)
    os.environ["FLAGS_enable_pir_api"] = "0"
    os.environ["FLAGS_use_onednn"] = "0"
    os.environ["FLAGS_use_mkldnn"] = "0"


def select_paddle_device(paddle_module: Any | None = None) -> str:
    """安装的是 CUDA 版 Paddle 时使用第一张 GPU，否则回退到 CPU。"""
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


def _to_numpy_image(image: Any) -> Any:
    try:
        import numpy as np
    except Exception as exc:
        raise PaddleOCRUnavailableError("缺少 numpy，无法将图片转换为 PaddleOCR 所需格式。") from exc

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
