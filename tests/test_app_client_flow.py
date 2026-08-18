import unittest

from app import SUPPORTED_FILE_TYPES, _run_ocr


class AppClientFlowTests(unittest.TestCase):
    def test_upload_page_supports_images_and_pdf(self):
        self.assertIn("pdf", SUPPORTED_FILE_TYPES)
        self.assertIn("png", SUPPORTED_FILE_TYPES)
        self.assertIn("jpg", SUPPORTED_FILE_TYPES)

    def test_run_ocr_uses_the_selected_client_and_returns_raw_json(self):
        class FakeClient:
            def __init__(self):
                self.calls = []

            def recognize(self, filename, file_bytes, *, visualize):
                self.calls.append((filename, file_bytes, visualize))
                return {"result": {"layoutParsingResults": []}}

        client = FakeClient()
        result = _run_ocr(client, "invoice.pdf", b"pdf-bytes", visualize=False)

        self.assertEqual(result, {"result": {"layoutParsingResults": []}})
        self.assertEqual(client.calls, [("invoice.pdf", b"pdf-bytes", False)])


if __name__ == "__main__":
    unittest.main()
