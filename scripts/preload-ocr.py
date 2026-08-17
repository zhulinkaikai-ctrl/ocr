from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from id_card_ocr.paddle_adapter import select_paddle_device
from id_card_ocr.paddleocr_vl_adapter import PaddleOCRVLAdapter
from ocr_api.settings import get_settings


def main() -> None:
    settings = get_settings()
    print(f"OCR engine: {settings.ocr_engine}")
    print(f"OCR device: {settings.ocr_device or select_paddle_device()}")
    print(f"Model cache: {settings.model_cache_dir}")

    # 初始化引擎会提前下载/加载 PaddleOCR-VL-1.6 模型，避免真实请求首次命中时变慢。
    PaddleOCRVLAdapter(enable_orientation=True)._get_engine()
    print("PaddleOCR-VL-1.6 模型预加载完成。")


if __name__ == "__main__":
    main()
