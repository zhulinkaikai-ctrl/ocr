import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class DeploymentSettingsTests(unittest.TestCase):
    def test_reads_deployment_env_overrides(self):
        from ocr_api.settings import AppSettings

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "OCR_DEVICE": "gpu:1",
                    "MODEL_CACHE_DIR": temp_dir,
                    "MAX_FILE_BYTES": "12345",
                    "LOG_LEVEL": "DEBUG",
                    "OCR_DETECTION_MODEL": "PP-OCRv6_medium_det",
                    "OCR_RECOGNITION_MODEL": "PP-OCRv6_medium_rec",
                },
                clear=True,
            ):
                settings = AppSettings.from_env()

        self.assertEqual(settings.ocr_device, "gpu:1")
        self.assertEqual(settings.model_cache_dir, Path(temp_dir))
        self.assertEqual(settings.max_file_bytes, 12345)
        self.assertEqual(settings.max_image_bytes, 12345)
        self.assertEqual(settings.log_level, "DEBUG")
        self.assertEqual(settings.ocr_detection_model, "PP-OCRv6_medium_det")
        self.assertEqual(settings.ocr_recognition_model, "PP-OCRv6_medium_rec")

    def test_rejects_invalid_max_file_bytes(self):
        from ocr_api.settings import AppSettings

        with patch.dict(os.environ, {"MAX_FILE_BYTES": "0"}, clear=True):
            with self.assertRaises(ValueError):
                AppSettings.from_env()

    def test_keeps_max_image_bytes_compatibility(self):
        from ocr_api.settings import AppSettings

        with patch.dict(os.environ, {"MAX_IMAGE_BYTES": "6789"}, clear=True):
            settings = AppSettings.from_env()

        self.assertEqual(settings.max_file_bytes, 6789)


if __name__ == "__main__":
    unittest.main()
