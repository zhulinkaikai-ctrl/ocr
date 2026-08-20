from __future__ import annotations

import base64
import unittest
from io import BytesIO

from PIL import Image

from ocr_api.file_loader import (
    FileInputError,
    decode_base64_file,
    materialize_file,
    validate_public_file_url,
)


class FileLoaderTests(unittest.TestCase):
    def test_decodes_png_data_url(self):
        buffer = BytesIO()
        Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

        uploaded = decode_base64_file(f"data:image/png;base64,{encoded}")

        self.assertEqual(uploaded.name, "upload.png")
        self.assertEqual(uploaded.suffix, ".png")
        self.assertEqual(uploaded.content_type, "image/png")
        self.assertEqual(uploaded.data[:8], b"\x89PNG\r\n\x1a\n")

    def test_accepts_pdf_bytes_and_materializes_temporary_file(self):
        uploaded = decode_base64_file(
            "data:application/pdf;base64,"
            + base64.b64encode(b"%PDF-1.7\n%test").decode("ascii")
        )

        self.assertEqual(uploaded.name, "upload.pdf")
        self.assertEqual(uploaded.suffix, ".pdf")
        self.assertEqual(uploaded.content_type, "application/pdf")

        with materialize_file(uploaded) as path:
            self.assertEqual(path.name, "upload.pdf")
            self.assertEqual(path.read_bytes(), b"%PDF-1.7\n%test")
            self.assertTrue(path.exists())

        self.assertFalse(path.exists())

    def test_rejects_unsupported_file_type(self):
        value = base64.b64encode(b"plain text").decode("ascii")

        with self.assertRaises(FileInputError):
            decode_base64_file(f"data:text/plain;base64,{value}")

    def test_rejects_localhost_url(self):
        with self.assertRaises(FileInputError):
            validate_public_file_url("http://127.0.0.1/file.pdf")

    def test_rejects_non_http_url(self):
        with self.assertRaises(FileInputError):
            validate_public_file_url("file:///tmp/file.pdf")

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(FileInputError):
            validate_public_file_url("https://user:pass@example.com/file.pdf")


if __name__ == "__main__":
    unittest.main()
