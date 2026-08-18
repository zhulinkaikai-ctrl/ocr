import base64
import importlib.util
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed")
class ApiRoutesTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from api_app import app
        from ocr_api.routes import get_ocr_adapter
        from ocr_api.settings import clear_settings_cache

        clear_settings_cache()
        self.addCleanup(clear_settings_cache)

        class FakeAdapter:
            def recognize(self, image):
                return {
                    "res": {
                        "page_index": None,
                        "parsing_res_list": [{"block_content": "姓名张三"}],
                    }
                }

        app.dependency_overrides[get_ocr_adapter] = lambda: FakeAdapter()
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], 200)

    def test_id_card_returns_paddleocr_vl_raw_json(self):
        response = self.client.post(
            "/api/v1/ocr/id-card",
            json={"orderNo": "ORDER-1", "imageBase64": _sample_png_base64()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "res": {
                    "page_index": None,
                    "parsing_res_list": [{"block_content": "姓名张三"}],
                }
            },
        )

    def test_business_license_returns_paddleocr_vl_raw_json(self):
        response = self.client.post(
            "/api/v1/ocr/business-license",
            json={"orderNo": "ORDER-2", "imageBase64": _sample_png_base64()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "res": {
                    "page_index": None,
                    "parsing_res_list": [{"block_content": "姓名张三"}],
                }
            },
        )

    def test_parameter_error_response(self):
        response = self.client.post("/api/v1/ocr/id-card", json={"orderNo": "ORDER-3"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["code"], 400)
        self.assertEqual(payload["data"]["result"], 1)

    def test_ignores_api_token_env(self):
        from ocr_api.settings import clear_settings_cache

        with patch.dict("os.environ", {"API_TOKEN": "secret-token"}, clear=False):
            clear_settings_cache()
            response = self.client.post(
                "/api/v1/ocr/id-card",
                json={"orderNo": "ORDER-1", "imageBase64": _sample_png_base64()},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["res"]["parsing_res_list"][0]["block_content"],
            "姓名张三",
        )

    def test_download_error_response(self):
        import ocr_api.routes as routes
        from ocr_api.image_loader import ImageDownloadError

        original = routes.load_request_image

        async def fail_download(*args, **kwargs):
            raise ImageDownloadError("download failed")

        routes.load_request_image = fail_download
        self.addCleanup(lambda: setattr(routes, "load_request_image", original))

        response = self.client.post(
            "/api/v1/ocr/id-card",
            json={"orderNo": "ORDER-3", "imageUrl": "https://example.com/a.png"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["code"], 1001)
        self.assertEqual(payload["msg"], "OCR识别异常")

    def test_logs_id_card_exception_in_chinese(self):
        from api_app import app
        from ocr_api.routes import get_ocr_adapter

        class BrokenAdapter:
            def recognize(self, image):
                raise RuntimeError("boom")

        app.dependency_overrides[get_ocr_adapter] = lambda: BrokenAdapter()

        with self.assertLogs("ocr_api.routes", level="ERROR") as logs:
            response = self.client.post(
                "/api/v1/ocr/id-card",
                json={"orderNo": "ORDER-LOG", "imageBase64": _sample_png_base64()},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("身份证 OCR 识别异常", "\n".join(logs.output))

    def test_logs_business_license_exception_in_chinese(self):
        from api_app import app
        from ocr_api.routes import get_ocr_adapter

        class BrokenAdapter:
            def recognize(self, image):
                raise RuntimeError("boom")

        app.dependency_overrides[get_ocr_adapter] = lambda: BrokenAdapter()

        with self.assertLogs("ocr_api.routes", level="ERROR") as logs:
            response = self.client.post(
                "/api/v1/ocr/business-license",
                json={"orderNo": "ORDER-LOG", "imageBase64": _sample_png_base64()},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("营业执照 OCR 识别异常", "\n".join(logs.output))

    def test_unversioned_routes_are_not_registered(self):
        self.assertEqual(self.client.get("/health").status_code, 404)
        self.assertEqual(
            self.client.post("/ocr/id-card", json={"orderNo": "ORDER-OLD"}).status_code,
            404,
        )


def _sample_png_base64() -> str:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


if __name__ == "__main__":
    unittest.main()
