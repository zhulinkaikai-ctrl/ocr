import unittest

from id_card_ocr.models import ExtractedField, IDCardResult, OCRLine
from ocr_api.responses import (
    build_business_license_success,
    build_error,
    build_id_card_success,
)


class ApiResponseTests(unittest.TestCase):
    def test_builds_id_card_response_with_external_field_names(self):
        result = IDCardResult(
            side="正面",
            fields=[
                ExtractedField("name", "姓名", "张三", "通过", 0.99),
                ExtractedField("gender", "性别", "男", "通过", 0.98),
                ExtractedField("ethnicity", "民族", "汉", "通过", 0.98),
                ExtractedField("birth_date", "出生日期", "1981年08月16日", "通过", 0.97),
                ExtractedField("address", "住址", "浙江省杭州市", "通过", 0.96),
                ExtractedField("id_number", "公民身份号码", "330101198108160011", "通过", 0.95),
            ],
        )

        payload = build_id_card_success("ORDER-1", result)

        self.assertEqual(payload["msg"], "成功")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["result"], 0)
        self.assertEqual(payload["data"]["side"], "front")
        self.assertEqual(payload["data"]["orderNo"], "ORDER-1")
        self.assertEqual(payload["data"]["info"]["name"], "张三")
        self.assertEqual(payload["data"]["info"]["year"], "1981")
        self.assertEqual(payload["data"]["info"]["month"], "8")
        self.assertEqual(payload["data"]["info"]["day"], "16")
        self.assertEqual(payload["data"]["info"]["number"], "330101198108160011")

    def test_builds_business_license_response_with_content(self):
        content = {"enterprise_name": "上海市测试店", "credit_code": "91310000TEST"}

        payload = build_business_license_success("ORDER-2", content)

        self.assertEqual(payload["data"]["content"], content)
        self.assertEqual(payload["data"]["orderNo"], "ORDER-2")
        self.assertEqual(payload["data"]["result"], 0)

    def test_builds_error_response(self):
        payload = build_error("ORDER-3", 400, "参数错误")

        self.assertEqual(
            payload,
            {
                "msg": "参数错误",
                "success": False,
                "code": 400,
                "data": {"result": 1, "orderNo": "ORDER-3"},
            },
        )


if __name__ == "__main__":
    unittest.main()
