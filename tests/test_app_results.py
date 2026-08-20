from __future__ import annotations

import unittest


class AppResultTests(unittest.TestCase):
    def test_collapses_single_raw_result_for_display(self):
        from app import build_display_payload

        payload = build_display_payload([{"res": {"rec_texts": ["原始文本"]}}])

        self.assertEqual(payload, {"res": {"rec_texts": ["原始文本"]}})

    def test_keeps_multi_page_raw_results_for_display(self):
        from app import build_display_payload

        payload = build_display_payload(
            [
                {"res": {"page_index": 0}},
                {"res": {"page_index": 1}},
            ]
        )

        self.assertEqual(
            payload,
            [
                {"res": {"page_index": 0}},
                {"res": {"page_index": 1}},
            ],
        )


if __name__ == "__main__":
    unittest.main()
