from __future__ import annotations

from pydantic import BaseModel, Field


class OCRRequest(BaseModel):
    orderNo: str | None = Field(default=None, description="调用方订单号；为空时服务端自动生成")
    imageBase64: str | None = Field(default=None, description="图片 Base64，支持 data URL 前缀")
    imageUrl: str | None = Field(default=None, description="公网 http/https 图片 URL")

