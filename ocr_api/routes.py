from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends

from id_card_ocr.paddleocr_vl_adapter import PaddleOCRVLAdapter

from .image_loader import ImageDownloadError, ImageInputError, load_request_image
from .responses import build_error
from .schemas import OCRRequest


logger = logging.getLogger(__name__)
router = APIRouter()


@lru_cache(maxsize=1)
def get_ocr_adapter() -> PaddleOCRVLAdapter:
    """创建 OCR 适配器。

    PaddleOCR-VL 模型体积较大，服务进程内只创建一个延迟初始化的适配器。测试时
    仍可通过 FastAPI 依赖覆盖替换为 FakeAdapter，不会加载真实模型。
    """
    return PaddleOCRVLAdapter(enable_orientation=True)


@router.get("/health")
async def health() -> dict[str, int]:
    return {"status": 200}


@router.post("/ocr/id-card")
async def recognize_id_card(
    request: OCRRequest,
    adapter: Annotated[PaddleOCRVLAdapter, Depends(get_ocr_adapter)],
) -> Any:
    """识别身份证，并直接返回 PaddleOCR-VL 原始 JSON。"""
    return await _recognize_raw_json(request, adapter, "身份证")


@router.post("/ocr/business-license")
async def recognize_business_license(
    request: OCRRequest,
    adapter: Annotated[PaddleOCRVLAdapter, Depends(get_ocr_adapter)],
) -> Any:
    """识别营业执照，并直接返回 PaddleOCR-VL 原始 JSON。"""
    return await _recognize_raw_json(request, adapter, "营业执照")


async def _recognize_raw_json(
    request: OCRRequest,
    adapter: PaddleOCRVLAdapter,
    document_name: str,
) -> Any:
    """加载请求图片并透传模型原始 JSON，不做业务字段提取或成功响应包装。"""
    order_no = _order_no(request.orderNo)
    try:
        # 请求支持 imageBase64 和 imageUrl 两种来源；这里会做格式、大小和 URL 安全校验。
        image = await load_request_image(request.imageBase64, request.imageUrl)
    except ImageInputError:
        return build_error(order_no, 400, "参数错误")
    except ImageDownloadError:
        return build_error(order_no, 1001, "OCR识别异常")

    try:
        return adapter.recognize(image)
    except Exception:
        logger.exception("%s OCR 识别异常，orderNo=%s", document_name, order_no)
        return build_error(order_no, 1001, "OCR识别异常")


def _order_no(value: str | None) -> str:
    """优先使用调用方订单号；没有传时生成一个便于日志追踪的编号。"""
    if value and value.strip():
        return value.strip()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    return f"{timestamp}{uuid4().hex[:6]}"

