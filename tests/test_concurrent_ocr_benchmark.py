from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from scripts.concurrent_ocr_benchmark import (
    BenchmarkFile,
    RequestResult,
    build_request_payloads,
    load_benchmark_files,
    parse_args,
    result_from_response,
    summarize_results,
)


class ConcurrentOCRBenchmarkTests(unittest.TestCase):
    """压测脚本的纯函数测试，不向真实 OCR 服务发请求。"""

    def test_load_benchmark_files_encodes_local_images_and_pdfs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.7\n%sample")

            # 只需要 PDF 文件头就能覆盖本地文件读取和 Base64 编码逻辑。
            files = load_benchmark_files([pdf_path])

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "sample.pdf")
        self.assertEqual(base64.b64decode(files[0].file_base64), b"%PDF-1.7\n%sample")

    def test_build_request_payloads_round_robins_files_and_adds_order_no(self):
        files = [
            BenchmarkFile(path=Path("a.png"), name="a.png", file_base64="AAA"),
            BenchmarkFile(path=Path("b.pdf"), name="b.pdf", file_base64="BBB"),
        ]

        payloads = build_request_payloads(files, total=5, order_prefix="bench")

        # 多文件压测按轮询分配，确保图片和 PDF 都会被覆盖到。
        self.assertEqual([item.file_name for item in payloads], ["a.png", "b.pdf", "a.png", "b.pdf", "a.png"])
        self.assertEqual(payloads[0].json, {"orderNo": "bench-000001", "file": "AAA"})
        self.assertEqual(payloads[-1].json, {"orderNo": "bench-000005", "file": "AAA"})

    def test_result_from_response_treats_serving_error_as_failure(self):
        result = result_from_response(
            status_code=200,
            body={"errorCode": 1001, "errorMsg": "OCR识别异常"},
            elapsed_ms=12.5,
            file_name="sample.png",
        )

        # 官方服务化响应可能仍是 HTTP 200，errorCode 非 0 要按失败处理。
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "serving_error_1001: OCR识别异常")

    def test_summarize_results_calculates_latency_and_error_counts(self):
        # 固定三条耗时，便于验证平均值、百分位和错误聚合口径。
        summary = summarize_results(
            [
                RequestResult(ok=True, status_code=200, elapsed_ms=10.0, file_name="a.png"),
                RequestResult(ok=True, status_code=200, elapsed_ms=20.0, file_name="a.png"),
                RequestResult(
                    ok=False,
                    status_code=500,
                    elapsed_ms=30.0,
                    file_name="b.pdf",
                    error="http_500",
                ),
            ]
        )

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.succeeded, 2)
        self.assertEqual(summary.failed, 1)
        self.assertEqual(summary.avg_ms, 20.0)
        self.assertEqual(summary.p50_ms, 20.0)
        self.assertEqual(summary.p95_ms, 30.0)
        self.assertEqual(summary.status_counts, {"200": 2, "500": 1})
        self.assertEqual(summary.error_counts, {"http_500": 1})

    def test_parse_args_accepts_required_benchmark_options(self):
        # CLI 参数解析单独测，避免脚本入口和测试里各写一套默认值。
        args = parse_args(
            [
                "--files",
                "a.png",
                "b.pdf",
                "--concurrency",
                "8",
                "--total",
                "40",
                "--endpoint",
                "http://localhost:8000/layout-parsing",
            ]
        )

        self.assertEqual(args.files, [Path("a.png"), Path("b.pdf")])
        self.assertEqual(args.concurrency, 8)
        self.assertEqual(args.total, 40)
        self.assertEqual(args.endpoint, "http://localhost:8000/layout-parsing")


if __name__ == "__main__":
    unittest.main()
