import unittest

from native_ocr import build_layout_parsing_response


class NativeOCRTests(unittest.TestCase):
    def test_builds_official_like_response_for_single_raw_result(self):
        response = build_layout_parsing_response({"res": {"parsing_res_list": []}})

        self.assertEqual(
            response,
            {
                "result": {
                    "layoutParsingResults": [
                        {"prunedResult": {"res": {"parsing_res_list": []}}}
                    ]
                }
            },
        )

    def test_builds_official_like_response_for_multiple_raw_results(self):
        response = build_layout_parsing_response(
            [{"res": {"page_index": 0}}, {"res": {"page_index": 1}}]
        )

        pages = response["result"]["layoutParsingResults"]
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0]["prunedResult"]["res"]["page_index"], 0)
        self.assertEqual(pages[1]["prunedResult"]["res"]["page_index"], 1)


if __name__ == "__main__":
    unittest.main()
