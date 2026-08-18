import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from env_file import load_env_file


class EnvFileTests(unittest.TestCase):
    def test_loads_key_values_without_overriding_existing_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "OCR_SERVICE_URL=http://127.0.0.1:9000\n"
                "EXISTING_VALUE=from-file\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"EXISTING_VALUE": "from-env"}, clear=True):
                loaded = load_env_file(env_path)

                self.assertTrue(loaded)
                self.assertEqual(os.environ["OCR_SERVICE_URL"], "http://127.0.0.1:9000")
                self.assertEqual(os.environ["EXISTING_VALUE"], "from-env")

    def test_returns_false_when_file_is_missing(self):
        self.assertFalse(load_env_file("missing.env"))


if __name__ == "__main__":
    unittest.main()
