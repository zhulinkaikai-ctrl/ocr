from __future__ import annotations

from id_card_ocr.paddle_adapter import PaddleOCRAdapter, select_paddle_device
from ocr_api.settings import get_settings


def main() -> None:
    settings = get_settings()
    print(f"OCR device: {settings.ocr_device or select_paddle_device()}")
    print(f"Model cache: {settings.model_cache_dir}")

    # Initializing the engine downloads/loads PaddleOCR models before real traffic arrives.
    PaddleOCRAdapter(lang="ch", enable_orientation=True)._get_engine()
    print("PaddleOCR preload finished.")


if __name__ == "__main__":
    main()
