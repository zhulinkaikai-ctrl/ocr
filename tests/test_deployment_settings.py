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
                    "MAX_IMAGE_BYTES": "12345",
                    "LOG_LEVEL": "DEBUG",
                },
                clear=False,
            ):
                settings = AppSettings.from_env()

        self.assertEqual(settings.ocr_device, "gpu:1")
        self.assertEqual(settings.model_cache_dir, Path(temp_dir))
        self.assertEqual(settings.max_image_bytes, 12345)
        self.assertEqual(settings.log_level, "DEBUG")

    def test_rejects_invalid_max_image_bytes(self):
        from ocr_api.settings import AppSettings

        with patch.dict(os.environ, {"MAX_IMAGE_BYTES": "0"}, clear=False):
            with self.assertRaises(ValueError):
                AppSettings.from_env()


if __name__ == "__main__":
    unittest.main()
