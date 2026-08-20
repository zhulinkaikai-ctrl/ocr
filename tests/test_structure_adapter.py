from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ocr_api.settings import clear_settings_cache


class StructureAdapterTests(unittest.TestCase):
    def setUp(self):
        clear_settings_cache()
        self.addCleanup(clear_settings_cache)

    def test_returns_raw_json_safe_results(self):
        from ocr_api.adapter import PPStructureV3Adapter

        captured: dict[str, object] = {}

        class FakeResult:
            @property
            def json(self):
                return {
                    "res": {
                        "input_path": Path("sample.pdf"),
                        "rec_texts": ["原始文本"],
                        "rec_scores": [0.98],
                    }
                }

        class FakePipeline:
            def __init__(self, **kwargs):
                captured["kwargs"] = kwargs

            def predict(self, input_path):
                captured["input"] = input_path
                return [FakeResult()]

        with patch.dict(sys.modules, {"paddleocr": types.SimpleNamespace(PPStructureV3=FakePipeline)}):
            adapter = PPStructureV3Adapter()
            result = adapter.recognize(Path("sample.pdf"))

        self.assertEqual(captured["input"], "sample.pdf")
        self.assertEqual(
            result,
            [
                {
                    "res": {
                        "input_path": "sample.pdf",
                        "rec_texts": ["原始文本"],
                        "rec_scores": [0.98],
                    }
                }
            ],
        )
        self.assertEqual(captured["kwargs"]["lang"], "ch")
        self.assertTrue(captured["kwargs"]["use_doc_orientation_classify"])
        self.assertTrue(captured["kwargs"]["use_textline_orientation"])
        self.assertTrue(captured["kwargs"]["use_table_recognition"])

    def test_serializes_numpy_scalars_and_arrays(self):
        import numpy as np
        from ocr_api.adapter import PPStructureV3Adapter

        class FakeResult:
            @property
            def json(self):
                return {
                    "res": {
                        "score": np.float32(0.75),
                        "box": np.array([[1, 2], [3, 4]], dtype=np.int32),
                    }
                }

        class FakePipeline:
            def __init__(self, **kwargs):
                pass

            def predict(self, input_path):
                return [FakeResult()]

        with patch.dict(sys.modules, {"paddleocr": types.SimpleNamespace(PPStructureV3=FakePipeline)}):
            result = PPStructureV3Adapter().recognize(Path("sample.png"))

        self.assertEqual(result, [{"res": {"score": 0.75, "box": [[1, 2], [3, 4]]}}])


if __name__ == "__main__":
    unittest.main()
