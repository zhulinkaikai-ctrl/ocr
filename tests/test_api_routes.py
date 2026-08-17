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
                from id_card_ocr.models import OCRLine

                return [
                    OCRLine("姓名张三", 0.99),
                    OCRLine("性别男民族汉", 0.98),
                    OCRLine("出生1981年8月16日", 0.97),
                    OCRLine("住址浙江省杭州市", 0.96),
                    OCRLine("公民身份号码11010519491231002X", 0.95),
                ]

        app.dependency_overrides[get_ocr_adapter] = lambda: FakeAdapter()
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_id_card_success_response(self):
        response = self.client.post(
            "/api/v1/ocr/id-card",
            json={"orderNo": "ORDER-1", "imageBase64": _sample_png_base64()},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["side"], "front")
        self.assertEqual(payload["data"]["info"]["name"], "张三")

    def test_parameter_error_response(self):
        response = self.client.post("/api/v1/ocr/id-card", json={"orderNo": "ORDER-2"})

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
        self.assertTrue(response.json()["success"])

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
