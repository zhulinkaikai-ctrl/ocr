import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from id_card_ocr.paddle_adapter import select_paddle_device
from id_card_ocr.paddleocr_vl_adapter import PaddleOCRVLAdapter
from ocr_api.settings import clear_settings_cache


class PaddleAdapterEnvTests(unittest.TestCase):
    def setUp(self):
        clear_settings_cache()
        self.addCleanup(clear_settings_cache)

    def test_sets_runtime_env_before_importing_paddleocr(self):
        captured = {}

        class FakePaddleOCRVL:
            def __init__(self, **kwargs):
                captured["kwargs"] = kwargs
                captured["pir"] = os.environ.get("FLAGS_enable_pir_api")
                captured["onednn"] = os.environ.get("FLAGS_use_onednn")
                captured["mkldnn"] = os.environ.get("FLAGS_use_mkldnn")
                captured["cache_home"] = os.environ.get("PADDLE_PDX_CACHE_HOME")

        fake_module = types.SimpleNamespace(PaddleOCRVL=FakePaddleOCRVL)

        with patch.dict(sys.modules, {"paddleocr": fake_module}):
            with patch.dict(
                os.environ,
                {
                    "FLAGS_enable_pir_api": "1",
                    "FLAGS_use_onednn": "1",
                    "FLAGS_use_mkldnn": "1",
                },
                clear=False,
            ):
                adapter = PaddleOCRVLAdapter(enable_orientation=False)
                adapter._get_engine()

        self.assertEqual(captured["pir"], "0")
        self.assertEqual(captured["onednn"], "0")
        self.assertEqual(captured["mkldnn"], "0")
        self.assertEqual(Path(captured["cache_home"]).name, ".paddlex_cache")
        self.assertEqual(captured["kwargs"]["pipeline_version"], "v1.6")
        self.assertFalse(captured["kwargs"]["use_queues"])

    def test_selects_gpu_when_paddle_has_cuda(self):
        fake_paddle = types.SimpleNamespace(is_compiled_with_cuda=MagicMock(return_value=True))

        self.assertEqual(select_paddle_device(fake_paddle), "gpu:0")

    def test_selects_cpu_when_paddle_has_no_cuda(self):
        fake_paddle = types.SimpleNamespace(is_compiled_with_cuda=MagicMock(return_value=False))

        self.assertEqual(select_paddle_device(fake_paddle), "cpu")

    def test_deployment_env_can_override_device(self):
        fake_paddle = types.SimpleNamespace(is_compiled_with_cuda=MagicMock(return_value=False))

        with patch.dict(os.environ, {"OCR_DEVICE": "gpu:0"}, clear=False):
            clear_settings_cache()
            self.assertEqual(select_paddle_device(fake_paddle), "gpu:0")


if __name__ == "__main__":
    unittest.main()
