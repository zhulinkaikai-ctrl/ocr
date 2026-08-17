from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STATUS_OK = "通过"
STATUS_MISSING = "缺失"
STATUS_SUSPICIOUS = "疑似错误"


@dataclass(frozen=True)
class OCRLine:
    """OCR 引擎识别出来的一行文字。

    text 是文字内容，confidence 是这一行的置信度，box 是文本框坐标。
    字段提取器只强依赖 text，后两项主要用于页面展示和排查问题。
    """

    text: str
    confidence: float | None = None
    box: Any | None = None


@dataclass(frozen=True)
class ExtractedField:
    """身份证字段提取结果，例如姓名、住址、公民身份号码。"""

    key: str
    label: str
    value: str
    status: str
    confidence: float | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "status": self.status,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class IDCardResult:
    """一张身份证图片的结构化识别结果。"""

    doc_type: str = "居民身份证"
    side: str = "未知"
    fields: list[ExtractedField] = field(default_factory=list)
    raw_texts: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "证件类型": self.doc_type,
            "证件面": self.side,
            "字段": [item.to_json_dict() for item in self.fields],
            "原始文本": self.raw_texts,
        }
