import unittest

from id_card_ocr.extractor import extract_id_card
from id_card_ocr.models import OCRLine


class ExtractorTests(unittest.TestCase):
    def test_extracts_front_side_fields(self):
        lines = [
            OCRLine(text="姓名张三", confidence=0.99),
            OCRLine(text="性别男民族汉", confidence=0.98),
            OCRLine(text="出生1949年12月31日", confidence=0.97),
            OCRLine(text="住址北京市朝阳区幸福路100号", confidence=0.96),
            OCRLine(text="公民身份号码11010519491231002X", confidence=0.95),
        ]

        result = extract_id_card(lines)
        payload = result.to_json_dict()
        fields = {field["label"]: field for field in payload["字段"]}

        self.assertEqual(payload["证件类型"], "居民身份证")
        self.assertEqual(payload["证件面"], "正面")
        self.assertEqual(fields["姓名"]["key"], "name")
        self.assertEqual(fields["姓名"]["value"], "张三")
        self.assertEqual(fields["性别"]["value"], "男")
        self.assertEqual(fields["民族"]["value"], "汉")
        self.assertEqual(fields["出生日期"]["value"], "1949年12月31日")
        self.assertEqual(fields["公民身份号码"]["value"], "11010519491231002X")
        self.assertEqual(fields["公民身份号码"]["status"], "通过")

    def test_extracts_back_side_fields(self):
        lines = [
            OCRLine(text="签发机关北京市公安局朝阳分局", confidence=0.96),
            OCRLine(text="有效期限2010.01.01-2030.01.01", confidence=0.95),
        ]

        result = extract_id_card(lines)
        payload = result.to_json_dict()
        fields = {field["label"]: field for field in payload["字段"]}

        self.assertEqual(payload["证件面"], "反面")
        self.assertEqual(fields["签发机关"]["key"], "issuing_authority")
        self.assertEqual(fields["签发机关"]["value"], "北京市公安局朝阳分局")
        self.assertEqual(fields["有效期限"]["value"], "2010.01.01-2030.01.01")

    def test_unknown_side_returns_missing_front_fields_by_default(self):
        result = extract_id_card([OCRLine(text="无法识别的文本", confidence=0.5)])
        payload = result.to_json_dict()

        self.assertEqual(payload["证件面"], "未知")
        self.assertEqual(payload["字段"][0]["status"], "缺失")


if __name__ == "__main__":
    unittest.main()
