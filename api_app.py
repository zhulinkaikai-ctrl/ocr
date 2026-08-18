from __future__ import annotations

import base64
import binascii
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from env_file import load_env_file
from native_ocr import NativeOCRUnavailableError, NativePaddleOCRVLRecognizer


load_env_file()

app = FastAPI(title="PaddleOCR-VL Local API", version="0.1.0")


class LayoutParsingRequest(BaseModel):
    """官方 layout-parsing 兼容请求体。"""

    file: str
    fileType: int
    visualize: bool = False


@lru_cache(maxsize=1)
def get_recognizer() -> NativePaddleOCRVLRecognizer:
    """模型较大，进程内只初始化一次。"""
    return NativePaddleOCRVLRecognizer()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/layout-parsing")
async def layout_parsing(
    request: LayoutParsingRequest,
    recognizer: Annotated[NativePaddleOCRVLRecognizer, Depends(get_recognizer)],
) -> dict:
    if request.fileType not in {0, 1}:
        raise HTTPException(status_code=400, detail="fileType 只支持 0(PDF) 或 1(图片)。")

    try:
        file_bytes = _decode_base64_file(request.file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return recognizer.recognize(
            file_bytes,
            request.fileType,
            visualize=request.visualize,
        )
    except NativeOCRUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _decode_base64_file(value: str) -> bytes:
    if "," in value and value.lower().lstrip().startswith("data:"):
        value = value.split(",", 1)[1]
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("file 必须是有效 Base64。") from exc
