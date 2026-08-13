from __future__ import annotations

import re
from datetime import date
from typing import Any

from id_card_ocr.models import IDCardResult


ID_CARD_INFO_KEYS = ["number", "address", "month", "nation", "year", "sex", "name", "day"]


def build_error(order_no: str, code: int, msg: str) -> dict[str, Any]:
    return {
        "msg": msg,
        "success": False,
        "code": code,
        "data": {"result": 1, "orderNo": order_no},
    }


def build_id_card_success(order_no: str, result: IDCardResult) -> dict[str, Any]:
    values = {field.key: field.value for field in result.fields}
    year, month, day = _split_birth_date(values.get("birth_date", ""))
    info = {
        "number": values.get("id_number", ""),
        "address": values.get("address", ""),
        "month": month,
        "nation": values.get("ethnicity", ""),
        "year": year,
        "sex": values.get("gender", ""),
        "name": values.get("name", ""),
        "day": day,
    }
    return {
        "msg": "成功",
        "success": True,
        "code": 200,
        "data": {
            "result": 0,
            "side": "front",
            "orderNo": order_no,
            "info": info,
        },
    }


def build_business_license_success(order_no: str, content: dict[str, Any]) -> dict[str, Any]:
    return {
        "msg": "成功",
        "success": True,
        "code": 200,
        "data": {
            "result": 0,
            "orderNo": order_no,
            "content": content,
        },
    }


def _split_birth_date(value: str) -> tuple[str, str, str]:
    match = re.search(r"((?:18|19|20)\d{2})[年./-]?(\d{1,2})[月./-]?(\d{1,2})日?", value or "")
    if not match:
        return "", "", ""
    year, month, day = (int(part) for part in match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return "", "", ""
    return str(year), str(month), str(day)

