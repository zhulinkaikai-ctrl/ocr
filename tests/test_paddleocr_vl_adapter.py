import unittest
from unittest.mock import patch

from PIL import Image

from id_card_ocr.paddleocr_vl_adapter import PaddleOCRVLAdapter


class PaddleOCRVLAdapterTests(unittest.TestCase):
    def test_recognize_returns_clean_json_for_single_result(self):
        class FakeResult:
            json = {"res": {"parsing_res_list": [{"block_content": "姓名张三"}]}}

            def to_json(self):
                return {"input_img": "should-not-be-used"}

        class FakeEngine:
            def predict(self, **kwargs):
                return [FakeResult()]

        adapter = PaddleOCRVLAdapter()
        adapter._engine = FakeEngine()

        result = adapter.recognize(Image.new("RGB", (16, 16), "white"))

        self.assertEqual(result, FakeResult.json)

    def test_recognize_prefers_json_property_on_dict_like_result(self):
        class FakeResult(dict):
            json = {"res": {"parsing_res_list": [{"block_content": "统一社会信用代码"}]}}

        class FakeEngine:
            def predict(self, **kwargs):
                return [FakeResult({"input_img": "should-not-be-used"})]

        adapter = PaddleOCRVLAdapter()
        adapter._engine = FakeEngine()

        result = adapter.recognize(Image.new("RGB", (16, 16), "white"))

        self.assertEqual(result, FakeResult.json)
        self.assertIs(type(result), dict)

    def test_recognize_returns_json_array_for_multiple_pages(self):
        class FakeResult:
            def __init__(self, page_index):
                self.json = {"res": {"page_index": page_index}}

        class FakeEngine:
            def predict(self, **kwargs):
                return [FakeResult(0), FakeResult(1)]

        adapter = PaddleOCRVLAdapter()
        adapter._engine = FakeEngine()

        result = adapter.recognize(Image.new("RGB", (16, 16), "white"))

        self.assertEqual(
            result,
            [{"res": {"page_index": 0}}, {"res": {"page_index": 1}}],
        )

    def test_recognize_applies_configured_local_image_compression(self):
        class FakeEngine:
            def __init__(self):
                self.input_shape = None

            def predict(self, *, input):
                self.input_shape = input.shape
                return [{"res": {"parsing_res_list": []}}]

        engine = FakeEngine()
        adapter = PaddleOCRVLAdapter()
        adapter._engine = engine

        with patch(
            "id_card_ocr.paddleocr_vl_adapter.get_settings",
            return_value=type("Settings", (), {"ocr_compress_max_side": 640})(),
        ):
            result = adapter.recognize(Image.new("RGB", (1600, 800), "white"))

        self.assertEqual(result, {"res": {"parsing_res_list": []}})
        self.assertLessEqual(max(engine.input_shape[:2]), 640)

    def test_recognize_keeps_original_image_without_compression(self):
        class FakeEngine:
            def __init__(self):
                self.input_shape = None

            def predict(self, *, input):
                self.input_shape = input.shape
                return [{"res": {"parsing_res_list": []}}]

        engine = FakeEngine()
        adapter = PaddleOCRVLAdapter()
        adapter._engine = engine

        with patch(
            "id_card_ocr.paddleocr_vl_adapter.get_settings",
            return_value=type("Settings", (), {"ocr_compress_max_side": None})(),
        ):
            adapter.recognize(Image.new("RGB", (1600, 800), "white"))

        self.assertEqual(engine.input_shape[:2], (800, 1600))

    def test_initializes_v16_pipeline_on_selected_gpu_without_queues(self):
        class FakePaddleOCRVL:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        adapter = PaddleOCRVLAdapter(pipeline_version="v1.6", enable_orientation=True)

        with patch("id_card_ocr.paddleocr_vl_adapter._configure_paddle_runtime"), patch(
            "id_card_ocr.paddleocr_vl_adapter.select_paddle_device",
            return_value="gpu:0",
        ), patch.dict(
            "sys.modules",
            {"paddleocr": type("Module", (), {"PaddleOCRVL": FakePaddleOCRVL})()},
        ):
            engine = adapter._get_engine()

        self.assertEqual(engine.kwargs["pipeline_version"], "v1.6")
        self.assertEqual(engine.kwargs["device"], "gpu:0")
        self.assertTrue(engine.kwargs["use_doc_orientation_classify"])
        self.assertFalse(engine.kwargs["use_queues"])


if __name__ == "__main__":
    unittest.main()
