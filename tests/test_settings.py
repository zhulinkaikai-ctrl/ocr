import os
import unittest
from unittest.mock import patch

from ocr_settings import clear_settings_cache, get_settings


class OCRSettingsTests(unittest.TestCase):
    def setUp(self):
        clear_settings_cache()
        self.addCleanup(clear_settings_cache)

    def test_defaults_to_local_docker_service(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = get_settings()

        self.assertEqual(settings.ocr_service_url, "http://127.0.0.1:8080")
        self.assertEqual(settings.ocr_service_timeout_seconds, 120)

    def test_reads_local_service_url_and_timeout_from_environment(self):
        with patch.dict(
            os.environ,
            {
                "OCR_SERVICE_URL": "http://localhost:9000/",
                "OCR_SERVICE_TIMEOUT_SECONDS": "45",
            },
            clear=True,
        ):
            settings = get_settings()

        self.assertEqual(settings.ocr_service_url, "http://localhost:9000")
        self.assertEqual(settings.ocr_service_timeout_seconds, 45)


if __name__ == "__main__":
    unittest.main()
