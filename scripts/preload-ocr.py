from __future__ import annotations

from id_card_ocr.paddle_adapter import PaddleOCRAdapter, select_paddle_device
from ocr_api.settings import get_settings


def main() -> None:
    settings = get_settings()
    print(f"OCR device: {settings.ocr_device or select_paddle_device()}")
    print(f"Model cache: {settings.model_cache_dir}")

    # 初始化引擎会提前下载/加载 PaddleOCR 模型，避免真实请求首次命中时变慢。
    PaddleOCRAdapter(lang="ch", enable_orientation=True)._get_engine()
    print("PaddleOCR 模型预加载完成。")


if __name__ == "__main__":
    main()
