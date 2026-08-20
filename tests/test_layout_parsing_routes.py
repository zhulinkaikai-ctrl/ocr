from __future__ import annotations

import base64
import importlib.util
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed")
class LayoutParsingRouteTests(unittest.TestCase):
    """FastAPI routes aligned with PaddleOCR's basic serving API shape."""

    def setUp(self):
        from fastapi.testclient import TestClient

        from api_app import app
        from ocr_api.routes import get_ocr_adapter
        from ocr_api.settings import clear_settings_cache

        clear_settings_cache()
        get_ocr_adapter.cache_clear()
        self.addCleanup(clear_settings_cache)
        self.addCleanup(get_ocr_adapter.cache_clear)

        class FakeAdapter:
            def recognize(self, input_path, **predict_options):
                input_name = Path(input_path).name
                common = {
                    "input_path": input_name,
                    "model_settings": {"use_table_recognition": predict_options.get("use_table_recognition")},
                    "parsing_res_list": [{"block_label": "text", "block_content": "原始文本"}],
                }
                if Path(input_path).suffix == ".pdf":
                    return [
                        {"res": {"page_index": 0, **common}},
                        {"res": {"page_index": 1, **common}},
                    ]
                return [{"res": {"page_index": None, **common}}]

        app.dependency_overrides[get_ocr_adapter] = lambda: FakeAdapter()
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def test_health_is_still_available_on_existing_path(self):
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": 200})

    def test_layout_parsing_returns_official_success_envelope_for_image(self):
        response = self.client.post(
            "/layout-parsing",
            json={"file": _sample_png_base64(), "fileType": 1},
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(body["logId"], str)
        self.assertEqual(body["errorCode"], 0)
        self.assertEqual(body["errorMsg"], "Success")
        self.assertEqual(body["result"]["dataInfo"], {"fileType": 1})
        self.assertEqual(
            body["result"]["layoutParsingResults"],
            [
                {
                    "prunedResult": {
                        "model_settings": {"use_table_recognition": None},
                        "parsing_res_list": [{"block_label": "text", "block_content": "原始文本"}],
                    },
                    "markdown": None,
                    "outputImages": {},
                    "inputImage": None,
                    "pageIndex": None,
                }
            ],
        )

    def test_pdf_keeps_page_results_in_official_result_list(self):
        response = self.client.post(
            "/layout-parsing",
            json={"file": _sample_pdf_base64(), "fileType": 0},
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["result"]["dataInfo"], {"fileType": 0})
        self.assertEqual([item["pageIndex"] for item in body["result"]["layoutParsingResults"]], [0, 1])

    def test_layout_parsing_maps_serving_options_to_predict_options(self):
        response = self.client.post(
            "/layout-parsing",
            json={"file": _sample_png_base64(), "useTableRecognition": False},
        )

        item = response.json()["result"]["layoutParsingResults"][0]
        self.assertEqual(item["prunedResult"]["model_settings"], {"use_table_recognition": False})

    def test_missing_file_returns_official_error_envelope(self):
        response = self.client.post("/layout-parsing", json={})

        body = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(body["logId"], str)
        self.assertEqual(body["errorCode"], 400)
        self.assertEqual(body["errorMsg"], "Bad Request")
        self.assertNotIn("result", body)

    def test_old_ocr_routes_are_removed(self):
        self.assertEqual(self.client.post("/api/v1/ocr/structure", json={}).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/ocr/id-card", json={}).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/ocr/business-license", json={}).status_code, 404)


def _sample_png_base64() -> str:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _sample_pdf_base64() -> str:
    return base64.b64encode(b"%PDF-1.7\n%test").decode("ascii")


if __name__ == "__main__":
    unittest.main()
