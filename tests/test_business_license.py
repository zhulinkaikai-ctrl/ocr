import unittest

from id_card_ocr.business_license import extract_business_license
from id_card_ocr.models import OCRLine


class BusinessLicenseTests(unittest.TestCase):
    def test_extracts_business_license_fields_and_normalizes_dates(self):
        lines = [
            OCRLine("营业执照", 0.99),
            OCRLine("名称上海市测试店", 0.98),
            OCRLine("类型个体工商户", 0.97),
            OCRLine("统一社会信用代码92430000TEST49E", 0.96),
            OCRLine("法定代表人赵三", 0.95),
            OCRLine("住所江西省南昌市测试路", 0.94),
            OCRLine("注册资本100万元", 0.93),
            OCRLine("成立日期2024年4月19日", 0.92),
            OCRLine("营业期限2024年4月19日至2034年4月18日", 0.91),
            OCRLine("经营范围许可项目：餐饮服务。", 0.90),
            OCRLine("组成形式个人经营", 0.89),
        ]

        content = extract_business_license(lines)

        self.assertEqual(content["enterprise_name"], "上海市测试店")
        self.assertEqual(content["enterprise_type"], "个体工商户")
        self.assertEqual(content["credit_code"], "92430000TEST49E")
        self.assertEqual(content["lR_name"], "赵三")
        self.assertEqual(content["establishing_date"], "2024-04-19")
        self.assertEqual(content["op_from"], "2024-04-19")
        self.assertEqual(content["op_to"], "2034-04-18")
        self.assertEqual(content["op_period"], "2024年04月19日 至 2034年04月18日")
        self.assertEqual(content["is_copy"], 0)

    def test_keeps_unknown_fields_and_missing_fields_stable(self):
        content = extract_business_license([OCRLine("名称只有名称")])

        self.assertEqual(content["enterprise_name"], "只有名称")
        self.assertEqual(content["credit_code"], "")
        self.assertEqual(content["registration_code"], "")
        self.assertEqual(content["is_copy"], 0)


if __name__ == "__main__":
    unittest.main()
