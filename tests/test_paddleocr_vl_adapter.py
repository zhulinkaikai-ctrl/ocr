import json
import os
import sys
import types
import unittest
from unittest.mock import patch

from PIL import Image

from id_card_ocr.paddleocr_vl_adapter import (
    PaddleOCRVLAdapter,
    normalize_paddleocr_vl_result,
)
from id_card_ocr.paddle_adapter import PaddleOCRUnavailableError
from ocr_api.settings import clear_settings_cache


class PaddleOCRVLAdapterTests(unittest.TestCase):
    def setUp(self):
        clear_settings_cache()
        self.addCleanup(clear_settings_cache)

    def test_normalizes_json_string_result(self):
        class FakeVLResult:
            def to_json(self):
                return json.dumps(
                    {
                        "res": {
                            "json": {
                                "parsing_res_list": [
                                    {"block_content": "姓名张三"},
                                    {"block_content": "公民身份号码11010519491231002X"},
                                ]
                            }
                        }
                    },
                    ensure_ascii=False,
                )

        lines = normalize_paddleocr_vl_result([FakeVLResult()])

        self.assertEqual([line.text for line in lines], ["姓名张三", "公民身份号码11010519491231002X"])

    def test_normalizes_service_style_layout_parsing_result(self):
        result = {
            "layoutParsingResults": [
                {
                    "prunedResult": {
                        "parsing_res_list": [
                            {"block_content": "姓名张三"},
                            {"block_content": "公民身份号码11010519491231002X"},
                        ]
                    }
                }
            ]
        }

        lines = normalize_paddleocr_vl_result([result])

        self.assertEqual([line.text for line in lines], ["姓名张三", "公民身份号码11010519491231002X"])

    def test_normalizes_markdown_attribute_when_json_is_unavailable(self):
        class FakeVLResult:
            markdown = {"text": "姓名张三\n公民身份号码11010519491231002X"}

        lines = normalize_paddleocr_vl_result([FakeVLResult()])

        self.assertEqual([line.text for line in lines], ["姓名张三\n公民身份号码11010519491231002X"])

    def test_initializes_paddleocr_vl_pipeline_lazily(self):
        captured = {}

        class FakePaddleOCRVL:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def predict(self, input):
                return []

        fake_module = types.SimpleNamespace(PaddleOCRVL=FakePaddleOCRVL)

        with patch.dict(sys.modules, {"paddleocr": fake_module}):
            with patch.dict(os.environ, {}, clear=False):
                with patch("id_card_ocr.paddleocr_vl_adapter.select_paddle_device", return_value="gpu:0"):
                    adapter = PaddleOCRVLAdapter(enable_orientation=False)
                    adapter._get_engine()

        self.assertEqual(captured["pipeline_version"], "v1.6")
        self.assertEqual(captured["device"], "gpu:0")
        self.assertFalse(captured["use_doc_orientation_classify"])
        self.assertTrue(captured["use_layout_detection"])
        self.assertFalse(captured["use_queues"])

    def test_dependency_error_keeps_paddlex_extra_hint(self):
        class FakePaddleOCRVL:
            def __init__(self, **kwargs):
                dependency_error = RuntimeError(
                    '`PaddleOCR-VL-1.6` requires additional dependencies. '
                    'To install them, run `pip install "paddlex[ocr]==3.7.2"`.'
                )
                raise RuntimeError("A dependency error occurred during pipeline creation.") from dependency_error

        fake_module = types.SimpleNamespace(PaddleOCRVL=FakePaddleOCRVL)

        with patch.dict(sys.modules, {"paddleocr": fake_module}):
            with self.assertRaises(PaddleOCRUnavailableError) as context:
                PaddleOCRVLAdapter()._get_engine()

        self.assertIn("paddlex[ocr]", str(context.exception))

    def test_compresses_image_only_when_local_env_sets_max_side(self):
        captured = {}

        class FakeEngine:
            def predict(self, **kwargs):
                captured.update(kwargs)
                return []

        with patch.dict(os.environ, {"OCR_COMPRESS_MAX_SIDE": "640"}, clear=False):
            clear_settings_cache()
            adapter = PaddleOCRVLAdapter()
            adapter._engine = FakeEngine()

            adapter.recognize(Image.new("RGB", (2000, 1000), "white"))

        height, width = captured["input"].shape[:2]
        self.assertEqual(max(width, height), 640)

    def test_keeps_original_image_when_compression_is_not_configured(self):
        captured = {}

        class FakeEngine:
            def predict(self, **kwargs):
                captured.update(kwargs)
                return []

        clear_settings_cache()
        adapter = PaddleOCRVLAdapter()
        adapter._engine = FakeEngine()

        adapter.recognize(Image.new("RGB", (2000, 1000), "white"))

        height, width = captured["input"].shape[:2]
        self.assertEqual((width, height), (2000, 1000))


if __name__ == "__main__":
    unittest.main()
