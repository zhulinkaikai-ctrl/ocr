import unittest

from id_card_ocr.validator import (
    validate_birth_date,
    validate_id_number,
)


class ValidatorTests(unittest.TestCase):
    def test_validates_id_number_checksum(self):
        result = validate_id_number("11010519491231002X")

        self.assertEqual(result, "通过")

    def test_rejects_bad_id_number_checksum(self):
        result = validate_id_number("110105194912310021")

        self.assertEqual(result, "疑似错误")

    def test_marks_missing_id_number(self):
        result = validate_id_number("")

        self.assertEqual(result, "缺失")

    def test_validates_birth_date(self):
        result = validate_birth_date("1949年12月31日")

        self.assertEqual(result, "通过")

    def test_rejects_invalid_birth_date(self):
        result = validate_birth_date("1949年13月31日")

        self.assertEqual(result, "疑似错误")


if __name__ == "__main__":
    unittest.main()
