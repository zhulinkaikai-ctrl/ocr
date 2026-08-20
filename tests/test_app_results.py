from __future__ import annotations

import unittest


class AppResultTests(unittest.TestCase):
    def test_wraps_single_raw_result_for_display_like_serving_response(self):
        from app import build_display_payload

        payload = build_display_payload([{"res": {"page_index": None, "rec_texts": ["原始文本"]}}])

        self.assertEqual(payload["errorCode"], 0)
        self.assertEqual(payload["errorMsg"], "Success")
        self.assertEqual(payload["result"]["dataInfo"], {"fileType": 1})
        self.assertEqual(
            payload["result"]["layoutParsingResults"],
            [
                {
                    "prunedResult": {"rec_texts": ["原始文本"]},
                    "markdown": None,
                    "outputImages": {},
                    "inputImage": None,
                    "pageIndex": None,
                }
            ],
        )

    def test_keeps_multi_page_raw_results_in_layout_parsing_results(self):
        from app import build_display_payload

        payload = build_display_payload(
            [
                {"res": {"page_index": 0}},
                {"res": {"page_index": 1}},
            ]
        )

        self.assertEqual(
            [item["pageIndex"] for item in payload["result"]["layoutParsingResults"]],
            [0, 1],
        )


if __name__ == "__main__":
    unittest.main()
