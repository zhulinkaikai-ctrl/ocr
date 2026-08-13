from __future__ import annotations

import re
from datetime import date

from .models import STATUS_MISSING, STATUS_OK, STATUS_SUSPICIOUS


# 身份证第 18 位校验码算法使用的固定权重和映射表。
# 规则来源是中国居民身份证号码校验位计算方法。
ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
ID_CHECK_CODES = "10X98765432"


def normalize_id_number(value: str) -> str:
    """去掉空白并把末尾 x 统一转成 X。"""
    return re.sub(r"\s+", "", value or "").upper()


def validate_required(value: str) -> str:
    """普通必填字段只判断是否为空。"""
    return STATUS_OK if (value or "").strip() else STATUS_MISSING


def validate_id_number(value: str) -> str:
    """校验身份证号格式、出生日期和最后一位校验码。"""
    value = normalize_id_number(value)
    if not value:
        return STATUS_MISSING
    if not re.fullmatch(r"\d{17}[\dX]", value):
        return STATUS_SUSPICIOUS

    birth = value[6:14]
    if not _is_valid_yyyymmdd(birth):
        return STATUS_SUSPICIOUS

    # 前 17 位分别乘以固定权重，求和后对 11 取余，再映射出应有的校验位。
    total = sum(int(value[index]) * ID_WEIGHTS[index] for index in range(17))
    expected = ID_CHECK_CODES[total % 11]
    return STATUS_OK if value[-1] == expected else STATUS_SUSPICIOUS


def validate_birth_date(value: str) -> str:
    """出生日期能解析成真实日期才算通过。"""
    if not (value or "").strip():
        return STATUS_MISSING
    parsed = parse_date(value)
    return STATUS_OK if parsed is not None else STATUS_SUSPICIOUS


def validate_valid_period(value: str) -> str:
    """身份证反面有效期限，支持“长期”或两个有效日期。"""
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
    """把出生日期统一成 YYYY年MM月DD日，解析失败则保留原文。"""
    parsed = parse_date(value)
    if parsed is None:
        return (value or "").strip()
    return f"{parsed.year:04d}年{parsed.month:02d}月{parsed.day:02d}日"


def parse_date(value: str) -> date | None:
    """解析中文、斜杠、横杠和点号分隔的年月日。"""
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
