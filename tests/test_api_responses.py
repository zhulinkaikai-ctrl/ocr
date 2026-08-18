import unittest

from ocr_api.responses import build_error


class ApiResponseTests(unittest.TestCase):
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
