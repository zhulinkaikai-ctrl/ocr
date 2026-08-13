from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from id_card_ocr.business_license import extract_business_license
from id_card_ocr.extractor import extract_id_card
from id_card_ocr.paddle_adapter import PaddleOCRAdapter

from .image_loader import ImageDownloadError, ImageInputError, load_request_image
from .responses import (
    build_business_license_success,
    build_error,
    build_id_card_success,
)
from .schemas import OCRRequest


logger = logging.getLogger(__name__)
router = APIRouter()


def get_ocr_adapter() -> PaddleOCRAdapter:
    return PaddleOCRAdapter(lang="ch", enable_orientation=True)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ocr/id-card")
async def recognize_id_card(
    request: OCRRequest,
    adapter: Annotated[PaddleOCRAdapter, Depends(get_ocr_adapter)],
) -> dict:
    order_no = _order_no(request.orderNo)
    try:
        image = await load_request_image(request.imageBase64, request.imageUrl)
    except ImageInputError:
        return build_error(order_no, 400, "参数错误")
    except ImageDownloadError:
        return build_error(order_no, 1001, "OCR识别异常")

    try:
        lines = adapter.recognize(image)
        result = extract_id_card(lines)
        if not _has_any_id_card_value(result):
            return build_error(order_no, 1001, "OCR识别异常")
        return build_id_card_success(order_no, result)
    except Exception:
        logger.exception("ID-card OCR failed, orderNo=%s", order_no)
        return build_error(order_no, 1001, "OCR识别异常")


@router.post("/ocr/business-license")
async def recognize_business_license(
    request: OCRRequest,
    adapter: Annotated[PaddleOCRAdapter, Depends(get_ocr_adapter)],
) -> dict:
    order_no = _order_no(request.orderNo)
    try:
        image = await load_request_image(request.imageBase64, request.imageUrl)
    except ImageInputError:
        return build_error(order_no, 400, "参数错误")
    except ImageDownloadError:
        return build_error(order_no, 1001, "OCR识别异常")

    try:
        lines = adapter.recognize(image)
        content = extract_business_license(lines)
        if not _has_any_business_license_value(content):
            return build_error(order_no, 1001, "OCR识别异常")
        return build_business_license_success(order_no, content)
    except Exception:
        logger.exception("Business-license OCR failed, orderNo=%s", order_no)
        return build_error(order_no, 1001, "OCR识别异常")


def _order_no(value: str | None) -> str:
    if value and value.strip():
        return value.strip()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    return f"{timestamp}{uuid4().hex[:6]}"


def _has_any_id_card_value(result) -> bool:
    return any(field.value for field in result.fields if field.key in {"name", "id_number", "address"})


def _has_any_business_license_value(content: dict) -> bool:
    return any(
        content.get(key)
        for key in ["credit_code", "enterprise_name", "lR_name", "address", "op_scope"]
    )
