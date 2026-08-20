from __future__ import annotations

from typing import Any
from uuid import uuid4


def build_success(layout_results: list[dict[str, Any]], file_type: int) -> dict[str, Any]:
    return {
        "logId": _log_id(),
        "errorCode": 0,
        "errorMsg": "Success",
        "result": {
            "layoutParsingResults": [_to_layout_parsing_result(item) for item in layout_results],
            "dataInfo": {"fileType": file_type},
        },
    }


def build_error(status_code: int, message: str) -> dict[str, Any]:
    return {
        "logId": _log_id(),
        "errorCode": status_code,
        "errorMsg": message,
    }


def _to_layout_parsing_result(item: dict[str, Any]) -> dict[str, Any]:
    res = item.get("res", item)
    if not isinstance(res, dict):
        res = {"res": res}

    pruned_result = {
        key: value
        for key, value in res.items()
        if key
        not in {
            "input_path",
            "page_index",
            "markdown",
            "outputImages",
            "output_images",
            "inputImage",
            "input_image",
        }
    }
    return {
        "prunedResult": pruned_result,
        "markdown": res.get("markdown"),
        "outputImages": res.get("outputImages", res.get("output_images", {})),
        "inputImage": res.get("inputImage", res.get("input_image")),
        "pageIndex": res.get("page_index"),
    }


def _log_id() -> str:
    return uuid4().hex
