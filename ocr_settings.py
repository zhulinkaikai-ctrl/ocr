from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class OCRSettings:
    """本地 Docker OCR 服务的连接配置。"""

    ocr_service_url: str
    ocr_service_timeout_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> OCRSettings:
    service_url = os.getenv("OCR_SERVICE_URL", "http://127.0.0.1:8080").rstrip("/")
    timeout = int(os.getenv("OCR_SERVICE_TIMEOUT_SECONDS", "120"))
    return OCRSettings(
        ocr_service_url=service_url,
        ocr_service_timeout_seconds=timeout,
    )


def clear_settings_cache() -> None:
    """测试或切换环境变量后刷新缓存。"""
    get_settings.cache_clear()
