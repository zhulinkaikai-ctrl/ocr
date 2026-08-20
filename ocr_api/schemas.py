from __future__ import annotations

from pydantic import BaseModel, Field


class OCRRequest(BaseModel):
    """OCR request body.

    New callers should use fileBase64 or fileUrl. imageBase64/imageUrl stay as
    compatibility aliases for the historical Java integration.
    """

    orderNo: str | None = Field(default=None, description="调用方订单号；为空时服务端自动生成")
    fileBase64: str | None = Field(default=None, description="图片或 PDF Base64，支持 data URL 前缀")
    fileUrl: str | None = Field(default=None, description="公网 http/https 图片或 PDF URL")
    imageBase64: str | None = Field(default=None, description="兼容旧字段：图片 Base64")
    imageUrl: str | None = Field(default=None, description="兼容旧字段：公网图片 URL")
