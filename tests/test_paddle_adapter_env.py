import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from id_card_ocr.paddle_adapter import PaddleOCRAdapter, select_paddle_device
from ocr_api.settings import clear_settings_cache


class PaddleAdapterEnvTests(unittest.TestCase):
    def setUp(self):
        clear_settings_cache()
        self.addCleanup(clear_settings_cache)

    def test_sets_runtime_env_before_importing_paddleocr(self):
        captured = {}

        class FakePaddleOCR:
            def __init__(self, **kwargs):
                captured["kwargs"] = kwargs
                captured["pir"] = os.environ.get("FLAGS_enable_pir_api")
                captured["onednn"] = os.environ.get("FLAGS_use_onednn")
                captured["mkldnn"] = os.environ.get("FLAGS_use_mkldnn")
                captured["cache_home"] = os.environ.get("PADDLE_PDX_CACHE_HOME")

            def predict(self, image):
                return []

        fake_module = types.SimpleNamespace(PaddleOCR=FakePaddleOCR)

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
                adapter = PaddleOCRAdapter(enable_orientation=False)
                adapter._get_engine()

        self.assertEqual(captured["pir"], "0")
        self.assertEqual(captured["onednn"], "0")
        self.assertEqual(captured["mkldnn"], "0")
        self.assertEqual(Path(captured["cache_home"]).name, ".paddlex_cache")
        self.assertIn("enable_mkldnn", captured["kwargs"])
        self.assertFalse(captured["kwargs"]["enable_mkldnn"])

    def test_does_not_fall_back_to_ocr_when_predict_returns_empty(self):
        class FakeEngine:
            def predict(self, image):
                return []

            def ocr(self, *args, **kwargs):
                raise AssertionError("ocr should not be called when predict already ran")

        adapter = PaddleOCRAdapter(enable_orientation=False)
        adapter._engine = FakeEngine()

        result = adapter.recognize(object())

        self.assertEqual(result, [])

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
