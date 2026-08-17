import os
import unittest
from unittest.mock import patch

from ocr_api.settings import clear_settings_cache, get_settings


class OCREngineSelectionTests(unittest.TestCase):
    def setUp(self):
        clear_settings_cache()
        self.addCleanup(clear_settings_cache)

    def test_default_engine_is_paddleocr_vl(self):
        self.assertEqual(get_settings().ocr_engine, "paddleocr_vl")

    def test_reads_vl_engine_alias_from_env(self):
        with patch.dict(os.environ, {"OCR_ENGINE": "paddleocr_vl"}, clear=False):
            clear_settings_cache()

            self.assertEqual(getattr(get_settings(), "ocr_engine", None), "paddleocr_vl")

    def test_rejects_plain_paddleocr_engine(self):
        with patch.dict(os.environ, {"OCR_ENGINE": "paddleocr"}, clear=False):
            clear_settings_cache()

            with self.assertRaises(ValueError):
                get_settings()

    def test_routes_create_vl_adapter_by_default(self):
        from ocr_api.routes import get_ocr_adapter

        adapter = get_ocr_adapter()

        self.assertEqual(adapter.__class__.__name__, "PaddleOCRVLAdapter")


if __name__ == "__main__":
    unittest.main()
