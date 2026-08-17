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
    """创建 OCR 适配器。

    这个函数单独存在，是为了使用 FastAPI 的依赖注入：
    正式运行时返回真实 PaddleOCR，测试时可以替换成 FakeAdapter，
    避免每次跑接口测试都加载大模型。
    """
    return PaddleOCRAdapter(lang="ch", enable_orientation=True)


@router.get("/health")
async def health() -> dict[str, str]:
    """供部署平台或调用方检查服务进程是否存活。"""
    return {"status": "ok"}


@router.post("/ocr/id-card")
async def recognize_id_card(
    request: OCRRequest,
    adapter: Annotated[PaddleOCRAdapter, Depends(get_ocr_adapter)],
) -> dict:
    """识别身份证，并返回双方约定的统一响应结构。"""
    order_no = _order_no(request.orderNo)
    try:
        # 请求支持 imageBase64 和 imageUrl 两种来源。
        # load_request_image 会完成格式、大小和 URL 安全校验。
        image = await load_request_image(request.imageBase64, request.imageUrl)
    except ImageInputError:
        # 图片缺失、Base64 非法、URL 指向内网等都属于参数问题。
        return build_error(order_no, 400, "参数错误")
    except ImageDownloadError:
        # URL 合法但远端下载失败，按约定归类为 OCR 识别异常。
        return build_error(order_no, 1001, "OCR识别异常")

    try:
        # 第一步：PaddleOCR 把图片转成若干 OCRLine。
        # 第二步：extract_id_card 再从文本行中提取姓名、证件号等业务字段。
        lines = adapter.recognize(image)
        result = extract_id_card(lines)
        if not _has_any_id_card_value(result):
            # OCR 没报异常但一个核心字段都没有，也不能返回“识别成功”。
            return build_error(order_no, 1001, "OCR识别异常")
        return build_id_card_success(order_no, result)
    except Exception:
        # 对外不暴露底层堆栈或模型信息，详细异常只记到服务日志。
        logger.exception("ID-card OCR failed, orderNo=%s", order_no)
        return build_error(order_no, 1001, "OCR识别异常")


@router.post("/ocr/business-license")
async def recognize_business_license(
    request: OCRRequest,
    adapter: Annotated[PaddleOCRAdapter, Depends(get_ocr_adapter)],
) -> dict:
    """识别营业执照，并返回 content 字段集合。"""
    order_no = _order_no(request.orderNo)
    try:
        image = await load_request_image(request.imageBase64, request.imageUrl)
    except ImageInputError:
        return build_error(order_no, 400, "参数错误")
    except ImageDownloadError:
        return build_error(order_no, 1001, "OCR识别异常")

    try:
        # OCR 模型只负责识字；营业执照字段匹配由规则提取器负责。
        lines = adapter.recognize(image)
        content = extract_business_license(lines)
        if not _has_any_business_license_value(content):
            return build_error(order_no, 1001, "OCR识别异常")
        return build_business_license_success(order_no, content)
    except Exception:
        logger.exception("Business-license OCR failed, orderNo=%s", order_no)
        return build_error(order_no, 1001, "OCR识别异常")


def _order_no(value: str | None) -> str:
    """优先使用调用方订单号；没有传时生成一个便于日志追踪的编号。"""
    if value and value.strip():
        return value.strip()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    return f"{timestamp}{uuid4().hex[:6]}"


def _has_any_id_card_value(result) -> bool:
    # 判断成功时只看最有代表性的核心字段，避免因为辅助字段误识别而返回成功。
    return any(field.value for field in result.fields if field.key in {"name", "id_number", "address"})


def _has_any_business_license_value(content: dict) -> bool:
    # 营业执照版的“最低成功标准”：至少识别出一个核心业务字段。
    return any(
        content.get(key)
        for key in ["credit_code", "enterprise_name", "lR_name", "address", "op_scope"]
    )
