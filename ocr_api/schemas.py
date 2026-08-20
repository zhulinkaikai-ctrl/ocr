from __future__ import annotations

from pydantic import BaseModel, Field


class LayoutParsingRequest(BaseModel):
    """Request body compatible with PaddleOCR's basic serving endpoint."""

    file: str | None = Field(default=None, description="图片/PDF Base64，data URL，或公网 URL")
    fileType: int | None = Field(default=None, description="0 表示 PDF，1 表示图片；为空时按文件内容推断")
    visualize: bool | None = Field(default=None, description="是否返回可视化图片")
    useDocOrientationClassify: bool | None = None
    useDocUnwarping: bool | None = None
    useTextlineOrientation: bool | None = None
    useSealRecognition: bool | None = None
    useTableRecognition: bool | None = None
    useFormulaRecognition: bool | None = None
    useChartRecognition: bool | None = None
    useRegionDetection: bool | None = None
    formatBlockContent: bool | None = None
