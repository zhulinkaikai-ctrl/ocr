from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class OCRSettings:
    """OCR 服务配置。"""

    ocr_service_url: str
    ocr_service_timeout_seconds: int
    ocr_device: str | None
    model_cache_dir: str
    ocr_compress_max_side: int | None


@lru_cache(maxsize=1)
def get_settings() -> OCRSettings:
    service_url = os.getenv("OCR_SERVICE_URL", "http://127.0.0.1:8080").rstrip("/")
    timeout = int(os.getenv("OCR_SERVICE_TIMEOUT_SECONDS", "120"))
    return OCRSettings(
        ocr_service_url=service_url,
        ocr_service_timeout_seconds=timeout,
        ocr_device=_empty_to_none(os.getenv("OCR_DEVICE", "gpu:0")),
        model_cache_dir=os.getenv("MODEL_CACHE_DIR", ".paddlex_cache"),
        ocr_compress_max_side=_optional_int(os.getenv("OCR_COMPRESS_MAX_SIDE")),
    )


def clear_settings_cache() -> None:
    """测试或切换环境变量后刷新缓存。"""
    get_settings.cache_clear()


def _empty_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)
