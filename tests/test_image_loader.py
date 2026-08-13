import base64
import unittest

from PIL import Image
from io import BytesIO

from ocr_api.image_loader import (
    ImageInputError,
    decode_base64_image,
    validate_public_image_url,
)


class ImageLoaderTests(unittest.TestCase):
    def test_decodes_data_url_image(self):
        buffer = BytesIO()
        Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

        image = decode_base64_image(f"data:image/png;base64,{encoded}")

        self.assertEqual(image.size, (2, 2))
        self.assertEqual(image.format, "PNG")

    def test_rejects_invalid_base64(self):
        with self.assertRaises(ImageInputError):
            decode_base64_image("not-base64")

    def test_rejects_localhost_url(self):
        with self.assertRaises(ImageInputError):
            validate_public_image_url("http://127.0.0.1/image.png")

    def test_rejects_non_http_url(self):
        with self.assertRaises(ImageInputError):
            validate_public_image_url("file:///tmp/image.png")


if __name__ == "__main__":
    unittest.main()
