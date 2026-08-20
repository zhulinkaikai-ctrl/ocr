from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from .adapter import PPStructureV3Adapter, collapse_raw_results
from .file_loader import FileDownloadError, FileInputError, load_request_file, materialize_file
from .responses import build_error
from .schemas import OCRRequest


logger = logging.getLogger(__name__)
router = APIRouter()


@lru_cache(maxsize=1)
def get_ocr_adapter() -> PPStructureV3Adapter:
    """Return the process-wide OCR adapter; tests override this FastAPI dependency."""
    return PPStructureV3Adapter(lang="ch", enable_orientation=True)


@router.get("/health")
async def health() -> dict[str, int]:
    return {"status": 200}


@router.post("/ocr/structure")
async def recognize_structure(
    request: OCRRequest,
    adapter: Annotated[PPStructureV3Adapter, Depends(get_ocr_adapter)],
) -> dict | list[dict]:
    """Run PP-StructureV3 and return its raw JSON-safe result."""
    return await _recognize_raw(request, adapter)


@router.post("/ocr/id-card")
async def recognize_id_card(
    request: OCRRequest,
    adapter: Annotated[PPStructureV3Adapter, Depends(get_ocr_adapter)],
) -> dict | list[dict]:
    """Historical route alias; Java now parses the raw PP-StructureV3 JSON."""
    return await _recognize_raw(request, adapter)


@router.post("/ocr/business-license")
async def recognize_business_license(
    request: OCRRequest,
    adapter: Annotated[PPStructureV3Adapter, Depends(get_ocr_adapter)],
) -> dict | list[dict]:
    """Historical route alias; Java now parses the raw PP-StructureV3 JSON."""
    return await _recognize_raw(request, adapter)


async def _recognize_raw(
    request: OCRRequest,
    adapter: PPStructureV3Adapter,
) -> dict | list[dict]:
    order_no = _order_no(request.orderNo)
    try:
        uploaded = await load_request_file(
            request.fileBase64,
            request.fileUrl,
            request.imageBase64,
            request.imageUrl,
        )
    except FileInputError:
        return build_error(order_no, 400, "参数错误")
    except FileDownloadError:
        return build_error(order_no, 1001, "OCR识别异常")

    try:
        with materialize_file(uploaded) as input_path:
            raw_results = adapter.recognize(input_path)
        return collapse_raw_results(raw_results)
    except Exception:
        logger.exception("PP-StructureV3 OCR 识别异常，orderNo=%s", order_no)
        return build_error(order_no, 1001, "OCR识别异常")


def _order_no(value: str | None) -> str:
    """优先使用调用方订单号；没有传时生成一个便于日志追踪的编号。"""
    if value and value.strip():
        return value.strip()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    return f"{timestamp}{uuid4().hex[:6]}"
