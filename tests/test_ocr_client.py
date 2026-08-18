import base64
import unittest
from unittest.mock import Mock

from ocr_client import OCRClient, build_request_payload


class OCRClientTests(unittest.TestCase):
    def test_builds_image_payload_with_base64_and_image_file_type(self):
        payload = build_request_payload("license.png", b"image-bytes")

        self.assertEqual(payload["fileType"], 1)
        self.assertEqual(
            payload["file"],
            base64.b64encode(b"image-bytes").decode("ascii"),
        )
        self.assertFalse(payload["visualize"])

    def test_builds_pdf_payload_with_pdf_file_type(self):
        payload = build_request_payload("invoice.pdf", b"pdf-bytes", visualize=True)

        self.assertEqual(payload["fileType"], 0)
        self.assertEqual(
            payload["file"],
            base64.b64encode(b"pdf-bytes").decode("ascii"),
        )
        self.assertTrue(payload["visualize"])

    def test_posts_to_local_layout_parsing_service_and_returns_json(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "result": {"layoutParsingResults": [{"prunedResult": {"text": "发票"}}]}
        }
        session.post.return_value = response

        client = OCRClient(
            base_url="http://127.0.0.1:8080/",
            timeout_seconds=12,
            session=session,
        )

        result = client.recognize("invoice.pdf", b"pdf-bytes")

        self.assertEqual(result["result"]["layoutParsingResults"][0]["prunedResult"]["text"], "发票")
        session.post.assert_called_once_with(
            "http://127.0.0.1:8080/layout-parsing",
            json={
                "file": base64.b64encode(b"pdf-bytes").decode("ascii"),
                "fileType": 0,
                "visualize": False,
            },
            timeout=12,
        )
        response.raise_for_status.assert_called_once_with()

    def test_wraps_http_errors_in_chinese_client_error(self):
        session = Mock()
        session.post.side_effect = RuntimeError("connection refused")
        client = OCRClient(session=session)

        with self.assertRaisesRegex(RuntimeError, "OCR 服务请求失败"):
            client.recognize("id-card.jpg", b"image-bytes")


if __name__ == "__main__":
    unittest.main()
