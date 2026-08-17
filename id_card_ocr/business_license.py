from __future__ import annotations

import re
from datetime import date

from .models import OCRLine


# 返回字段固定存在，即使某一项没有识别到也返回空字符串。
# 这样外部调用方不需要判断某个 key 是否缺失。
BUSINESS_LICENSE_KEYS = [
    "enterprise_type",
    "address",
    "registration_capital",
    "op_to",
    "org_form",
    "op_scope",
    "establishing_date",
    "registration_code",
    "op_from",
    "credit_code",
    "lR_name",
    "op_period",
    "enterprise_name",
    "is_copy",
]


def extract_business_license(lines: list[OCRLine]) -> dict[str, str | int]:
    """从 OCR 文本行中提取营业执照字段。

    OCR 引擎只提供“识别到了哪些文字”。这里通过标签规则把文字转换成
    enterprise_name、credit_code、address 等 API 字段。
    """
    # OCR 常把标签和值识别在同一行，也可能拆成两行；先去掉空白方便统一匹配。
    raw_lines = [_compact(line.text) for line in lines if _compact(line.text)]
    joined = "\n".join(raw_lines)
    content: dict[str, str | int] = {key: "" for key in BUSINESS_LICENSE_KEYS}
    content["is_copy"] = 0

    content["credit_code"] = _extract_code(joined, ["统一社会信用代码", "社会信用代码"])
    content["registration_code"] = _extract_code(joined, ["注册号"])
    content["enterprise_name"] = _extract_by_labels(raw_lines, ["名称", "企业名称"], _common_stop_labels())
    content["enterprise_type"] = _extract_by_labels(raw_lines, ["类型", "企业类型"], _common_stop_labels())
    content["lR_name"] = _extract_by_labels(raw_lines, ["法定代表人", "经营者", "负责人"], _common_stop_labels())
    content["registration_capital"] = _extract_by_labels(raw_lines, ["注册资本", "资金数额"], _common_stop_labels())
    content["address"] = _extract_by_labels(raw_lines, ["住所", "经营场所", "地址"], ["经营范围", "组成形式", "营业期限"])
    content["op_scope"] = _extract_multiline(raw_lines, "经营范围", ["登记机关", "组成形式", "营业期限", "年月日"])
    content["org_form"] = _extract_by_labels(raw_lines, ["组成形式"], _common_stop_labels())

    # 日期对外尽量返回 YYYY-MM-DD；解析失败时保留 OCR 原文，避免直接丢失信息。
    establishing_raw = _extract_by_labels(raw_lines, ["成立日期", "成立时间", "注册日期"], _common_stop_labels())
    content["establishing_date"] = _normalize_date_or_raw(establishing_raw)

    # op_period 保存完整经营期限；op_from/op_to 则拆成便于程序处理的标准日期。
    op_period_raw = _extract_by_labels(raw_lines, ["营业期限", "经营期限", "营业日期"], ["经营范围", "登记机关"])
    op_period = _normalize_period(op_period_raw)
    content["op_period"] = op_period or op_period_raw
    op_from, op_to = _split_period_to_iso(op_period_raw)
    content["op_from"] = op_from
    content["op_to"] = op_to

    return content


def _extract_by_labels(lines: list[str], labels: list[str], stop_labels: list[str]) -> str:
    """找到任一标签并取后面的值，遇到下一个字段标签时截断。"""
    stop_labels = [item for item in stop_labels if item not in labels]
    for index, line in enumerate(lines):
        for label in labels:
            if label not in line:
                continue
            value = line.split(label, 1)[1]
            value = _trim_at_stop(value, stop_labels)
            if value:
                return value.strip(":：")
            if index + 1 < len(lines):
                # 有些版式会把“名称”和企业名称识别成相邻两行。
                return _trim_at_stop(lines[index + 1], stop_labels).strip(":：")
    return ""


def _extract_multiline(lines: list[str], label: str, stop_labels: list[str]) -> str:
    """提取可能跨多行的字段，当前主要用于内容较长的经营范围。"""
    parts: list[str] = []
    collecting = False
    for line in lines:
        text = line
        if label in text:
            collecting = True
            text = text.split(label, 1)[1]
        elif not collecting:
            continue

        if any(stop in text for stop in stop_labels):
            text = _trim_at_stop(text, stop_labels)
            if text:
                parts.append(text)
            break
        if text:
            parts.append(text)
    return "".join(parts).strip(":：")


def _extract_code(text: str, labels: list[str]) -> str:
    """优先按字段标签提取代码；标签漏识别时再匹配独立长编码。"""
    for label in labels:
        pattern = rf"{label}[:：]?\s*([0-9A-Z]{{6,32}})"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    match = re.search(r"\b[0-9A-Z]{15,32}\b", text, re.IGNORECASE)
    return match.group(0).upper() if match else ""


def _normalize_date_or_raw(value: str) -> str:
    parsed = _find_first_date(value)
    if parsed is None:
        return value
    return _to_iso(parsed)


def _normalize_period(value: str) -> str:
    # 只有同时找到开始、结束两个日期时才输出标准经营期限。
    dates = _find_dates(value)
    if len(dates) < 2:
        return ""
    return f"{_to_chinese_date(dates[0])} 至 {_to_chinese_date(dates[1])}"


def _split_period_to_iso(value: str) -> tuple[str, str]:
    dates = _find_dates(value)
    if len(dates) < 2:
        return "", ""
    return _to_iso(dates[0]), _to_iso(dates[1])


def _find_first_date(value: str) -> date | None:
    dates = _find_dates(value)
    return dates[0] if dates else None


def _find_dates(value: str) -> list[date]:
    """兼容 2024年4月19日、2024-04-19、2024/04/19 等常见格式。"""
    dates: list[date] = []
    for match in re.finditer(r"((?:18|19|20)\d{2})[年./-]?(\d{1,2})[月./-]?(\d{1,2})日?", value or ""):
        year, month, day = (int(part) for part in match.groups())
        try:
            dates.append(date(year, month, day))
        except ValueError:
            continue
    return dates


def _to_iso(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}-{value.day:02d}"


def _to_chinese_date(value: date) -> str:
    return f"{value.year:04d}年{value.month:02d}月{value.day:02d}日"


def _trim_at_stop(value: str, stop_labels: list[str]) -> str:
    # 同一 OCR 行可能包含多个字段，因此在最早出现的下一个标签处截断。
    positions = [value.find(label) for label in stop_labels if label in value]
    if positions:
        value = value[: min(positions)]
    return value.strip(":：,，。;；")


def _common_stop_labels() -> list[str]:
    return [
        "统一社会信用代码",
        "社会信用代码",
        "注册号",
        "名称",
        "企业名称",
        "类型",
        "企业类型",
        "法定代表人",
        "经营者",
        "负责人",
        "住所",
        "经营场所",
        "地址",
        "注册资本",
        "成立日期",
        "营业期限",
        "经营范围",
        "组成形式",
        "登记机关",
    ]


def _compact(value: str) -> str:
    return re.sub(r"[\s　]+", "", value or "")
