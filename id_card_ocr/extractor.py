from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import mean

from .models import (
    ExtractedField,
    IDCardResult,
    OCRLine,
    STATUS_MISSING,
)
from .validator import (
    normalize_birth_date,
    normalize_id_number,
    validate_birth_date,
    validate_id_number,
    validate_required,
    validate_valid_period,
)


@dataclass(frozen=True)
class FieldDef:
    key: str
    label: str


FRONT_FIELDS = [
    FieldDef("name", "姓名"),
    FieldDef("gender", "性别"),
    FieldDef("ethnicity", "民族"),
    FieldDef("birth_date", "出生日期"),
    FieldDef("address", "住址"),
    FieldDef("id_number", "公民身份号码"),
]

BACK_FIELDS = [
    FieldDef("issuing_authority", "签发机关"),
    FieldDef("valid_period", "有效期限"),
]


def extract_id_card(lines: list[OCRLine]) -> IDCardResult:
    side = detect_side(lines)
    raw_texts = [line.text for line in lines]

    if side == "反面":
        fields = _extract_back_fields(lines)
    else:
        fields = _extract_front_fields(lines)

    return IDCardResult(side=side, fields=fields, raw_texts=raw_texts)


def detect_side(lines: list[OCRLine]) -> str:
    text = "".join(_compact(line.text) for line in lines)
    front_score = sum(keyword in text for keyword in ["姓名", "性别", "民族", "出生", "住址", "公民身份号码", "身份号码"])
    back_score = sum(keyword in text for keyword in ["签发机关", "有效期限", "中华人民共和国"])

    if back_score > front_score:
        return "反面"
    if front_score > 0:
        return "正面"
    return "未知"


def _extract_front_fields(lines: list[OCRLine]) -> list[ExtractedField]:
    values: dict[str, tuple[str, float | None]] = {
        "name": _extract_after_label(lines, "姓名", stop_labels=["性别", "民族", "出生", "住址", "公民"]),
        "gender": _extract_gender(lines),
        "ethnicity": _extract_ethnicity(lines),
        "birth_date": _extract_birth_date(lines),
        "address": _extract_address(lines),
        "id_number": _extract_id_number(lines),
    }

    return [
        _make_field(definition, values.get(definition.key, ("", None)))
        for definition in FRONT_FIELDS
    ]


def _extract_back_fields(lines: list[OCRLine]) -> list[ExtractedField]:
    values: dict[str, tuple[str, float | None]] = {
        "issuing_authority": _extract_after_label(lines, "签发机关", stop_labels=["有效期限"]),
        "valid_period": _extract_valid_period(lines),
    }

    return [
        _make_field(definition, values.get(definition.key, ("", None)))
        for definition in BACK_FIELDS
    ]


def _make_field(definition: FieldDef, data: tuple[str, float | None]) -> ExtractedField:
    value, confidence = data
    status = _field_status(definition.key, value)
    return ExtractedField(
        key=definition.key,
        label=definition.label,
        value=value,
        status=status,
        confidence=_round_confidence(confidence),
    )


def _field_status(key: str, value: str) -> str:
    if key == "id_number":
        return validate_id_number(value)
    if key == "birth_date":
        return validate_birth_date(value)
    if key == "valid_period":
        return validate_valid_period(value)
    return validate_required(value)


def _extract_after_label(
    lines: list[OCRLine],
    label: str,
    stop_labels: list[str] | None = None,
) -> tuple[str, float | None]:
    stop_labels = stop_labels or []
    for index, line in enumerate(lines):
        text = _compact(line.text)
        if label not in text:
            continue

        value = text.split(label, 1)[1]
        value = _trim_at_stop_label(value, stop_labels)
        if value:
            return value, line.confidence

        if index + 1 < len(lines):
            return _compact(lines[index + 1].text), lines[index + 1].confidence
    return "", None


def _extract_gender(lines: list[OCRLine]) -> tuple[str, float | None]:
    for line in lines:
        text = _compact(line.text)
        match = re.search(r"性别[:：]?(男|女)", text)
        if match:
            return match.group(1), line.confidence
    return "", None


def _extract_ethnicity(lines: list[OCRLine]) -> tuple[str, float | None]:
    for line in lines:
        text = _compact(line.text)
        match = re.search(r"民族[:：]?([\u4e00-\u9fa5]{1,4})(?=$|出生|住址|公民|号码)", text)
        if match:
            return match.group(1), line.confidence
    return "", None


def _extract_birth_date(lines: list[OCRLine]) -> tuple[str, float | None]:
    for line in lines:
        text = _compact(line.text)
        if "出生" not in text:
            continue
        match = re.search(r"(?:18|19|20)\d{2}[年./-]?\d{1,2}[月./-]?\d{1,2}日?", text)
        if match:
            return normalize_birth_date(match.group(0)), line.confidence
    return "", None


def _extract_address(lines: list[OCRLine]) -> tuple[str, float | None]:
    parts: list[str] = []
    confidences: list[float] = []
    collecting = False

    for line in lines:
        text = _compact(line.text)
        if "公民身份号码" in text or "身份号码" in text or _find_id_number(text):
            break

        if "住址" in text:
            collecting = True
            text = text.split("住址", 1)[1]
        elif not collecting:
            continue

        if any(label in text for label in ["姓名", "性别", "民族", "出生"]):
            continue

        text = _trim_at_stop_label(text, ["公民身份号码", "身份号码"])
        if text:
            parts.append(text)
            if line.confidence is not None:
                confidences.append(line.confidence)

    if not parts:
        return "", None
    return "".join(parts), mean(confidences) if confidences else None


def _extract_id_number(lines: list[OCRLine]) -> tuple[str, float | None]:
    for line in lines:
        text = _compact(line.text)
        value = _find_id_number(text)
        if value:
            return normalize_id_number(value), line.confidence
    return "", None


def _extract_valid_period(lines: list[OCRLine]) -> tuple[str, float | None]:
    for index, line in enumerate(lines):
        text = _compact(line.text)
        if "有效期限" in text:
            value = text.split("有效期限", 1)[1]
            if value:
                return value, line.confidence
            if index + 1 < len(lines):
                return _compact(lines[index + 1].text), lines[index + 1].confidence

        match = re.search(r"(?:长期|(?:18|19|20)\d{2}[年./-]?\d{1,2}[月./-]?\d{1,2}日?.*)", text)
        if match:
            return match.group(1), line.confidence
    return "", None


def _find_id_number(text: str) -> str:
    match = re.search(r"[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]", text)
    return match.group(0) if match else ""


def _trim_at_stop_label(value: str, stop_labels: list[str]) -> str:
    stop_positions = [value.find(label) for label in stop_labels if label in value]
    if stop_positions:
        value = value[: min(stop_positions)]
    return value.strip(":：,，。;；")


def _compact(value: str) -> str:
    return re.sub(r"[\s　]+", "", value or "")


def _round_confidence(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)
