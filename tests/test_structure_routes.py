from __future__ import annotations

import base64
import importlib.util
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed")
class StructureRouteTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from api_app import app
        from ocr_api.routes import get_ocr_adapter
        from ocr_api.settings import clear_settings_cache

        clear_settings_cache()
        self.addCleanup(clear_settings_cache)

        class FakeAdapter:
            def recognize(self, input_path):
                input_name = Path(input_path).name
                if Path(input_path).suffix == ".pdf":
                    return [
                        {"res": {"page_index": 0, "input_path": input_name, "rec_texts": ["第一页原始文本"]}},
                        {"res": {"page_index": 1, "input_path": input_name, "rec_texts": ["第二页原始文本"]}},
                    ]
                return [{"res": {"input_path": input_name, "rec_texts": ["原始文本"]}}]

        app.dependency_overrides[get_ocr_adapter] = lambda: FakeAdapter()
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def test_health_is_unchanged(self):
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], 200)

    def test_structure_route_returns_raw_image_result(self):
        response = self.client.post(
            "/api/v1/ocr/structure",
            json={"orderNo": "ORDER-1", "fileBase64": _sample_png_base64()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"res": {"input_path": "upload.png", "rec_texts": ["原始文本"]}},
        )

    def test_pdf_returns_raw_page_result_list(self):
        response = self.client.post(
            "/api/v1/ocr/structure",
            json={"fileBase64": _sample_pdf_base64()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {"res": {"page_index": 0, "input_path": "upload.pdf", "rec_texts": ["第一页原始文本"]}},
                {"res": {"page_index": 1, "input_path": "upload.pdf", "rec_texts": ["第二页原始文本"]}},
            ],
        )

    def test_historical_routes_are_raw_result_aliases(self):
        for path in ("/api/v1/ocr/id-card", "/api/v1/ocr/business-license"):
            response = self.client.post(
                path,
                json={"imageBase64": _sample_png_base64()},
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"res": {"input_path": "upload.png", "rec_texts": ["原始文本"]}})

    def test_parameter_error_keeps_existing_error_envelope(self):
        response = self.client.post("/api/v1/ocr/structure", json={"orderNo": "ORDER-2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], 400)
        self.assertFalse(response.json()["success"])

    def test_unversioned_routes_are_not_registered(self):
        self.assertEqual(self.client.get("/health").status_code, 404)
        self.assertEqual(self.client.post("/ocr/structure", json={}).status_code, 404)


def _sample_png_base64() -> str:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _sample_pdf_base64() -> str:
    return "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.7\n%test").decode("ascii")


if __name__ == "__main__":
    unittest.main()
