import unittest

import app
from id_card_ocr.models import OCRLine


class DemoDocumentResultTests(unittest.TestCase):
    def test_builds_business_license_payload_with_raw_texts(self):
        lines = [
            OCRLine("名称上海市测试店", 0.98),
            OCRLine("统一社会信用代码91310000TEST", 0.97),
        ]

        payload = app.build_demo_document_result("营业执照", lines)

        self.assertEqual(payload["data"]["content"]["enterprise_name"], "上海市测试店")
        self.assertEqual(payload["data"]["content"]["credit_code"], "91310000TEST")
        self.assertEqual(
            payload["data"]["raw_texts"],
            ["名称上海市测试店", "统一社会信用代码91310000TEST"],
        )

    def test_includes_optional_vl_debug_snapshot_for_local_demo(self):
        lines = [
            OCRLine("名称上海市测试店", 0.98),
            OCRLine("统一社会信用代码91310000TEST", 0.97),
        ]
        debug_snapshot = [{"type": "FakeVLResult", "value": {"ok": True}}]

        payload = app.build_demo_document_result("营业执照", lines, debug_snapshot=debug_snapshot)

        self.assertEqual(payload["data"]["vl_debug"], debug_snapshot)


if __name__ == "__main__":
    unittest.main()
