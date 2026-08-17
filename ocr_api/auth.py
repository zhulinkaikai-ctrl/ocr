from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, status

from .settings import get_settings


def require_api_token(
    x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None,
) -> None:
    """可选 API Token 鉴权。

    未配置 API_TOKEN 时不启用鉴权，适合本地调试。
    配置 API_TOKEN 后，调用方必须在请求头里传 X-API-Token。
    """
    expected_token = get_settings().api_token
    if expected_token is None:
        return

    if x_api_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid api token",
        )
