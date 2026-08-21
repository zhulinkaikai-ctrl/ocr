from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ocr_api.settings import clear_settings_cache


class StructureAdapterTests(unittest.TestCase):
    """PP-StructureV3 适配器测试，用 fake pipeline 避免加载真实模型。"""

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
                # 捕获初始化参数，保护默认模型组合不被无意改回高风险配置。
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
        self.assertNotIn("lang", captured["kwargs"])
        self.assertEqual(captured["kwargs"]["text_detection_model_name"], "PP-OCRv6_medium_det")
        self.assertEqual(captured["kwargs"]["text_recognition_model_name"], "PP-OCRv6_medium_rec")
        self.assertEqual(captured["kwargs"]["cpu_threads"], 4)
        self.assertTrue(captured["kwargs"]["use_doc_orientation_classify"])
        self.assertTrue(captured["kwargs"]["use_textline_orientation"])
        self.assertTrue(captured["kwargs"]["use_table_recognition"])
        # 当前环境下这些增强模型初始化不稳定，默认关闭以保证 Java 调用可用。
        self.assertFalse(captured["kwargs"]["use_formula_recognition"])
        self.assertFalse(captured["kwargs"]["use_chart_recognition"])
        self.assertFalse(captured["kwargs"]["use_seal_recognition"])

    def test_serializes_numpy_scalars_and_arrays(self):
        import numpy as np
        from ocr_api.adapter import PPStructureV3Adapter

        class FakeResult:
            @property
            def json(self):
                # PaddleX 结果里常见 numpy 类型，返回 Java 前必须转成 JSON-safe 数据。
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
