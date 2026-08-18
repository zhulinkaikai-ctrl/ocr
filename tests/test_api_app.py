import base64
import importlib.util
import unittest


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed")
class ApiAppTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from api_app import app, get_recognizer

        class FakeRecognizer:
            def __init__(self):
                self.calls = []

            def recognize(self, file_bytes, file_type, *, visualize):
                self.calls.append((file_bytes, file_type, visualize))
                return {
                    "result": {
                        "layoutParsingResults": [
                            {"prunedResult": {"text": "统一社会信用代码"}}
                        ]
                    }
                }

        self.fake_recognizer = FakeRecognizer()
        app.dependency_overrides[get_recognizer] = lambda: self.fake_recognizer
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def test_health_uses_official_root_endpoint(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_layout_parsing_accepts_official_json_request(self):
        response = self.client.post(
            "/layout-parsing",
            json={
                "file": base64.b64encode(b"pdf-bytes").decode("ascii"),
                "fileType": 0,
                "visualize": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["result"]["layoutParsingResults"][0]["prunedResult"]["text"],
            "统一社会信用代码",
        )
        self.assertEqual(self.fake_recognizer.calls, [(b"pdf-bytes", 0, True)])

    def test_layout_parsing_rejects_invalid_base64(self):
        response = self.client.post(
            "/layout-parsing",
            json={"file": "not-base64", "fileType": 1},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Base64", response.json()["detail"])

    def test_layout_parsing_rejects_unknown_file_type(self):
        response = self.client.post(
            "/layout-parsing",
            json={
                "file": base64.b64encode(b"unknown").decode("ascii"),
                "fileType": 9,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("fileType", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
