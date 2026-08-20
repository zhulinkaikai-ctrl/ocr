from __future__ import annotations

import argparse
import asyncio
import base64
import math
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import httpx


DEFAULT_ENDPOINT = "http://127.0.0.1:8000/layout-parsing"


@dataclass(frozen=True)
class BenchmarkFile:
    path: Path
    name: str
    file_base64: str


@dataclass(frozen=True)
class RequestPayload:
    file_name: str
    json: dict[str, str]


@dataclass(frozen=True)
class RequestResult:
    ok: bool
    status_code: int | None
    elapsed_ms: float
    file_name: str
    error: str | None = None


@dataclass(frozen=True)
class BenchmarkSummary:
    total: int
    succeeded: int
    failed: int
    avg_ms: float
    min_ms: float
    max_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    qps: float
    status_counts: dict[str, int]
    error_counts: dict[str, int]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Concurrent benchmark tool for the PP-StructureV3 OCR API.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "Example: python scripts/concurrent_ocr_benchmark.py "
            "--files samples/a.png samples/b.pdf --concurrency 4 --total 20"
        ),
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="OCR API endpoint to benchmark.",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        type=Path,
        required=True,
        help="Local image/PDF files to send. Requests are distributed round-robin.",
    )
    parser.add_argument(
        "--concurrency",
        type=_positive_int,
        default=4,
        help="Number of concurrent in-flight HTTP requests.",
    )
    parser.add_argument(
        "--total",
        type=_positive_int,
        default=None,
        help="Total number of benchmark requests. Overrides --repeat when set.",
    )
    parser.add_argument(
        "--repeat",
        type=_positive_int,
        default=1,
        help="Requests per input file when --total is not set.",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=180.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--order-prefix",
        default="bench",
        help="Prefix used for generated orderNo values.",
    )

    args = parser.parse_args(argv)
    if args.total is None:
        args.total = len(args.files) * args.repeat
    return args


def load_benchmark_files(paths: Sequence[Path]) -> list[BenchmarkFile]:
    files: list[BenchmarkFile] = []
    for input_path in paths:
        path = input_path.expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"输入文件不存在：{input_path}")
        data = path.read_bytes()
        if not data:
            raise ValueError(f"输入文件为空：{input_path}")
        files.append(
            BenchmarkFile(
                path=path.resolve(),
                name=path.name,
                file_base64=base64.b64encode(data).decode("ascii"),
            )
        )
    if not files:
        raise ValueError("至少需要一个输入文件。")
    return files


def build_request_payloads(
    files: Sequence[BenchmarkFile],
    *,
    total: int,
    order_prefix: str,
) -> list[RequestPayload]:
    if total <= 0:
        raise ValueError("total 必须大于 0")
    if not files:
        raise ValueError("至少需要一个压测文件。")

    payloads: list[RequestPayload] = []
    for index in range(total):
        benchmark_file = files[index % len(files)]
        payloads.append(
            RequestPayload(
                file_name=benchmark_file.name,
                json={
                    "orderNo": f"{order_prefix}-{index + 1:06d}",
                    "file": benchmark_file.file_base64,
                },
            )
        )
    return payloads


async def run_benchmark(
    *,
    endpoint: str,
    payloads: Sequence[RequestPayload],
    concurrency: int,
    timeout: float,
) -> list[RequestResult]:
    if concurrency <= 0:
        raise ValueError("concurrency 必须大于 0")

    queue: asyncio.Queue[RequestPayload] = asyncio.Queue()
    for payload in payloads:
        queue.put_nowait(payload)

    results: list[RequestResult] = []
    results_lock = asyncio.Lock()
    worker_count = min(concurrency, max(1, len(payloads)))
    client_timeout = httpx.Timeout(timeout)
    limits = httpx.Limits(max_connections=worker_count, max_keepalive_connections=worker_count)

    async with httpx.AsyncClient(timeout=client_timeout, limits=limits) as client:
        workers = [
            asyncio.create_task(_worker(queue, results, results_lock, client, endpoint))
            for _ in range(worker_count)
        ]
        await queue.join()
        await asyncio.gather(*workers)
    return results


async def _worker(
    queue: asyncio.Queue[RequestPayload],
    results: list[RequestResult],
    results_lock: asyncio.Lock,
    client: httpx.AsyncClient,
    endpoint: str,
) -> None:
    while True:
        try:
            payload = queue.get_nowait()
        except asyncio.QueueEmpty:
            return

        try:
            result = await send_request(client, endpoint, payload)
            async with results_lock:
                results.append(result)
        finally:
            queue.task_done()


async def send_request(
    client: httpx.AsyncClient,
    endpoint: str,
    payload: RequestPayload,
) -> RequestResult:
    started = time.perf_counter()
    try:
        response = await client.post(endpoint, json=payload.json)
    except (httpx.HTTPError, asyncio.TimeoutError) as exc:
        elapsed_ms = _elapsed_ms(started)
        return RequestResult(
            ok=False,
            status_code=None,
            elapsed_ms=elapsed_ms,
            file_name=payload.file_name,
            error=f"{exc.__class__.__name__}: {exc}",
        )

    elapsed_ms = _elapsed_ms(started)
    body: Any
    try:
        body = response.json()
    except ValueError:
        body = None
    return result_from_response(
        status_code=response.status_code,
        body=body,
        elapsed_ms=elapsed_ms,
        file_name=payload.file_name,
    )


def result_from_response(
    *,
    status_code: int,
    body: Any,
    elapsed_ms: float,
    file_name: str,
) -> RequestResult:
    if 200 <= status_code < 300 and not _is_serving_failure(body):
        return RequestResult(ok=True, status_code=status_code, elapsed_ms=elapsed_ms, file_name=file_name)

    return RequestResult(
        ok=False,
        status_code=status_code,
        elapsed_ms=elapsed_ms,
        file_name=file_name,
        error=_error_from_response(status_code, body),
    )


def summarize_results(
    results: Sequence[RequestResult],
    *,
    wall_seconds: float | None = None,
) -> BenchmarkSummary:
    elapsed_values = [result.elapsed_ms for result in results]
    total = len(results)
    succeeded = sum(1 for result in results if result.ok)
    failed = total - succeeded
    wall = wall_seconds or 0.0
    return BenchmarkSummary(
        total=total,
        succeeded=succeeded,
        failed=failed,
        avg_ms=_round_ms(sum(elapsed_values) / total) if total else 0.0,
        min_ms=_round_ms(min(elapsed_values)) if elapsed_values else 0.0,
        max_ms=_round_ms(max(elapsed_values)) if elapsed_values else 0.0,
        p50_ms=_percentile(elapsed_values, 50),
        p95_ms=_percentile(elapsed_values, 95),
        p99_ms=_percentile(elapsed_values, 99),
        qps=round(total / wall, 2) if wall > 0 else 0.0,
        status_counts=_status_counts(results),
        error_counts=_error_counts(results),
    )


def format_summary(summary: BenchmarkSummary) -> str:
    lines = [
        "OCR concurrent benchmark result",
        f"total={summary.total} succeeded={summary.succeeded} failed={summary.failed} qps={summary.qps}",
        (
            "latency_ms "
            f"avg={summary.avg_ms} min={summary.min_ms} max={summary.max_ms} "
            f"p50={summary.p50_ms} p95={summary.p95_ms} p99={summary.p99_ms}"
        ),
        f"status_counts={summary.status_counts}",
    ]
    if summary.error_counts:
        lines.append(f"error_counts={summary.error_counts}")
    return "\n".join(lines)


async def async_main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    files = load_benchmark_files(args.files)
    payloads = build_request_payloads(files, total=args.total, order_prefix=args.order_prefix)

    print(f"endpoint={args.endpoint}")
    print(f"files={[file.name for file in files]}")
    print(f"concurrency={args.concurrency} total={args.total} timeout={args.timeout}s")

    started = time.perf_counter()
    results = await run_benchmark(
        endpoint=args.endpoint,
        payloads=payloads,
        concurrency=args.concurrency,
        timeout=args.timeout,
    )
    wall_seconds = time.perf_counter() - started

    summary = summarize_results(results, wall_seconds=wall_seconds)
    print(format_summary(summary))
    return 0 if summary.failed == 0 else 2


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return asyncio.run(async_main(argv))
    except KeyboardInterrupt:
        print("已中断。", file=sys.stderr)
        return 130
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"整数格式不正确：{value}") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须大于 0")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"小数格式不正确：{value}") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须大于 0")
    return parsed


def _elapsed_ms(started: float) -> float:
    return _round_ms((time.perf_counter() - started) * 1000)


def _is_serving_failure(body: Any) -> bool:
    return isinstance(body, dict) and body.get("errorCode", 0) != 0


def _error_from_response(status_code: int, body: Any) -> str:
    if _is_serving_failure(body):
        code = body.get("errorCode", "unknown")
        message = body.get("errorMsg")
        return f"serving_error_{code}: {message}" if message else f"serving_error_{code}"
    return f"http_{status_code}"


def _status_counts(results: Sequence[RequestResult]) -> dict[str, int]:
    counter = Counter("exception" if item.status_code is None else str(item.status_code) for item in results)
    return dict(counter)


def _error_counts(results: Sequence[RequestResult]) -> dict[str, int]:
    counter = Counter(item.error for item in results if item.error)
    return dict(counter)


def _percentile(values: Sequence[float], percentile: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = math.ceil((percentile / 100) * len(sorted_values)) - 1
    index = min(max(index, 0), len(sorted_values) - 1)
    return _round_ms(sorted_values[index])


def _round_ms(value: float) -> float:
    return round(value, 2)


if __name__ == "__main__":
    raise SystemExit(main())
