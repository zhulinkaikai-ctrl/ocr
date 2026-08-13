from __future__ import annotations

import re
from datetime import date

from .models import STATUS_MISSING, STATUS_OK, STATUS_SUSPICIOUS


ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
ID_CHECK_CODES = "10X98765432"


def normalize_id_number(value: str) -> str:
    return re.sub(r"\s+", "", value or "").upper()


def validate_required(value: str) -> str:
    return STATUS_OK if (value or "").strip() else STATUS_MISSING


def validate_id_number(value: str) -> str:
    value = normalize_id_number(value)
    if not value:
        return STATUS_MISSING
    if not re.fullmatch(r"\d{17}[\dX]", value):
        return STATUS_SUSPICIOUS

    birth = value[6:14]
    if not _is_valid_yyyymmdd(birth):
        return STATUS_SUSPICIOUS

    total = sum(int(value[index]) * ID_WEIGHTS[index] for index in range(17))
    expected = ID_CHECK_CODES[total % 11]
    return STATUS_OK if value[-1] == expected else STATUS_SUSPICIOUS


def validate_birth_date(value: str) -> str:
    if not (value or "").strip():
        return STATUS_MISSING
    parsed = parse_date(value)
    return STATUS_OK if parsed is not None else STATUS_SUSPICIOUS


def validate_valid_period(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return STATUS_MISSING
    if "长期" in value:
        return STATUS_OK

    dates = re.findall(r"(?:18|19|20)\d{2}[年./-]?\d{1,2}[月./-]?\d{1,2}日?", value)
    valid_dates = [parse_date(item) for item in dates]
    if dates and all(item is not None for item in valid_dates):
        return STATUS_OK
    return STATUS_SUSPICIOUS


def normalize_birth_date(value: str) -> str:
    parsed = parse_date(value)
    if parsed is None:
        return (value or "").strip()
    return f"{parsed.year:04d}年{parsed.month:02d}月{parsed.day:02d}日"


def parse_date(value: str) -> date | None:
    text = re.sub(r"\s+", "", value or "")
    match = re.search(r"((?:18|19|20)\d{2})[年./-]?(\d{1,2})[月./-]?(\d{1,2})日?", text)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _is_valid_yyyymmdd(value: str) -> bool:
    try:
        date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return False
    return True

