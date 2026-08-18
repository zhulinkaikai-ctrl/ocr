from __future__ import annotations

from typing import Any


def build_error(order_no: str, code: int, msg: str) -> dict[str, Any]:
    """构造统一失败响应；业务失败仍按约定返回 data.result = 1。"""
    return {
        "msg": msg,
        "success": False,
        "code": code,
        "data": {"result": 1, "orderNo": order_no},
    }
