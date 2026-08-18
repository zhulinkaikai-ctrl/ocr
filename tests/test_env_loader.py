import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class EnvLoaderTests(unittest.TestCase):
    def test_loads_key_values_from_env_file(self):
        from ocr_api.env_loader import load_env_file

        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env.local"
            env_file.write_text(
                "OCR_DEVICE=cpu\nOCR_COMPRESS_MAX_SIDE=1280\n# comment\n\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                self.assertTrue(load_env_file(env_file))

                self.assertEqual(os.environ["OCR_DEVICE"], "cpu")
                self.assertEqual(os.environ["OCR_COMPRESS_MAX_SIDE"], "1280")

    def test_does_not_override_existing_environment_values(self):
        from ocr_api.env_loader import load_env_file

        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("OCR_DEVICE=cpu\n", encoding="utf-8")

            with patch.dict(os.environ, {"OCR_DEVICE": "gpu:0"}, clear=True):
                self.assertTrue(load_env_file(env_file))

                self.assertEqual(os.environ["OCR_DEVICE"], "gpu:0")


if __name__ == "__main__":
    unittest.main()
