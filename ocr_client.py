from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import requests

from ocr_settings import get_settings


class OCRClientError(RuntimeError):
    """OCR 服务调用失败。"""


class OCRClient:
    """调用官方兼容的 PaddleOCR-VL HTTP 服务。"""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        session: requests.Session | Any | None = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.ocr_service_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.ocr_service_timeout_seconds
        self.session = session or requests.Session()

    def recognize(
        self,
        filename: str,
        file_bytes: bytes,
        *,
        visualize: bool = False,
    ) -> dict[str, Any]:
        """上传图片或 PDF，原样返回官方 PaddleOCR-VL JSON。"""
        payload = build_request_payload(filename, file_bytes, visualize=visualize)
        try:
            response = self.session.post(
                f"{self.base_url}/layout-parsing",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            result = response.json()
        except Exception as exc:
            raise OCRClientError(f"OCR 服务请求失败：{exc}") from exc

        if not isinstance(result, dict):
            raise OCRClientError("OCR 服务响应格式错误：响应不是 JSON 对象。")
        return result


def build_request_payload(
    filename: str,
    file_bytes: bytes,
    *,
    visualize: bool = False,
) -> dict[str, Any]:
    """按官方 layout-parsing 服务格式将文件内容编码为 JSON 请求体。"""
    return {
        "file": base64.b64encode(file_bytes).decode("ascii"),
        "fileType": 0 if Path(filename).suffix.lower() == ".pdf" else 1,
        "visualize": visualize,
    }
