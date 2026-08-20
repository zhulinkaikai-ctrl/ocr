from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_IMAGE_BYTES = DEFAULT_MAX_FILE_BYTES
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppSettings:
    """部署相关配置。

    这些值都可以通过环境变量覆盖，方便同一份代码部署到开发机、测试机和生产服务器。
    """

    log_level: str
    max_file_bytes: int
    model_cache_dir: Path
    ocr_device: str | None

    @property
    def max_image_bytes(self) -> int:
        return self.max_file_bytes

    @classmethod
    def from_env(cls) -> "AppSettings":
        """从当前进程环境变量读取配置。"""
        return cls(
            log_level=os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
            max_file_bytes=_max_file_bytes(),
            model_cache_dir=_path("MODEL_CACHE_DIR", PROJECT_ROOT / ".paddlex_cache"),
            ocr_device=_optional_text("OCR_DEVICE"),
        )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """缓存配置读取结果，避免每次请求都重复解析环境变量。"""
    return AppSettings.from_env()


def clear_settings_cache() -> None:
    """测试或重新加载配置时清空缓存。"""
    get_settings.cache_clear()


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc
    if value <= 0:
        raise ValueError(f"{name} 必须大于 0")
    return value


def _max_file_bytes() -> int:
    if os.environ.get("MAX_FILE_BYTES") is not None:
        return _positive_int("MAX_FILE_BYTES", DEFAULT_MAX_FILE_BYTES)
    return _positive_int("MAX_IMAGE_BYTES", DEFAULT_MAX_FILE_BYTES)


def _path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return Path(value).expanduser()


def _optional_text(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None
