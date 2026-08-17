from __future__ import annotations

import base64
import binascii
import ipaddress
import socket
from io import BytesIO
from typing import Iterable
from urllib.parse import urlparse

import httpx
from PIL import Image, UnidentifiedImageError

from .settings import DEFAULT_MAX_IMAGE_BYTES, get_settings

MAX_IMAGE_BYTES = DEFAULT_MAX_IMAGE_BYTES
# URL 下载时只接受常见图片 MIME 类型。最终仍会交给 Pillow 校验真实内容，
# 不能只相信远端服务器返回的 Content-Type。
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/bmp",
    "image/webp",
}


class ImageInputError(ValueError):
    """调用方提供的图片参数本身不合法。"""

    pass


class ImageDownloadError(RuntimeError):
    """图片 URL 合法，但网络下载过程失败。"""

    pass


def decode_base64_image(value: str) -> Image.Image:
    """把普通 Base64 或 data:image/... 格式解码为 RGB 图片。"""
    raw = (value or "").strip()
    if not raw:
        raise ImageInputError("empty base64 image")
    # 浏览器经常生成 data:image/png;base64,xxxx，需要先去掉逗号前的元信息。
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageInputError("invalid base64 image") from exc
    return decode_image_bytes(data)


def decode_image_bytes(data: bytes) -> Image.Image:
    """验证图片字节，并返回已完整载入内存的 RGB 图片。"""
    if not data or len(data) > get_settings().max_image_bytes:
        raise ImageInputError("invalid image size")
    try:
        # verify() 只做完整性检查，不解码像素；因此随后要重新 open 一次并 load()。
        image = Image.open(BytesIO(data))
        image.verify()
        image = Image.open(BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageInputError("invalid image content") from exc
    image_format = image.format
    converted = image.convert("RGB")
    converted.format = image_format
    return converted


def validate_public_image_url(url: str) -> str:
    """只允许访问公网 HTTP/HTTPS 图片，防止 SSRF 读取本机或内网服务。"""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ImageInputError("invalid image url")
    # URL 中嵌入用户名密码通常不是正常图片地址，也容易造成凭据泄露。
    if parsed.username or parsed.password:
        raise ImageInputError("invalid image url")

    # 域名可能解析成多个 IP，只要其中一个不是公网地址就拒绝。
    for address in _resolve_host(parsed.hostname):
        if not _is_public_address(address):
            raise ImageInputError("non-public image url")
    return parsed.geturl()


async def load_image_from_url(url: str) -> Image.Image:
    """下载公网图片；每一次重定向都重新做 URL 安全校验。"""
    current_url = validate_public_image_url(url)
    async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
        # 最多允许 4 次请求，防止恶意或错误配置造成无限重定向。
        for _ in range(4):
            try:
                response = await client.get(current_url)
            except httpx.HTTPError as exc:
                raise ImageDownloadError("failed to download image") from exc
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise ImageDownloadError("invalid redirect")
                # 不能让 httpx 自动跟随重定向，否则公网 URL 可能跳转到 127.0.0.1。
                current_url = validate_public_image_url(str(response.url.join(location)))
                continue

            if response.status_code >= 400:
                raise ImageDownloadError(f"download failed with status {response.status_code}")
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
                raise ImageInputError("invalid image content type")
            content = response.content
            if len(content) > get_settings().max_image_bytes:
                raise ImageInputError("image too large")
            return decode_image_bytes(content)
    raise ImageDownloadError("too many redirects")


async def load_request_image(image_base64: str | None, image_url: str | None) -> Image.Image:
    """从 API 请求中选择图片来源；同时传入时优先使用 Base64。"""
    if image_base64 and image_base64.strip():
        return decode_base64_image(image_base64)
    if image_url and image_url.strip():
        return await load_image_from_url(image_url)
    raise ImageInputError("missing image source")


def _resolve_host(hostname: str) -> Iterable[ipaddress._BaseAddress]:
    """把域名解析成全部 IPv4/IPv6 地址，供公网地址检查使用。"""
    try:
        return [
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        ]
    except (socket.gaierror, ValueError) as exc:
        raise ImageInputError("invalid image url host") from exc


def _is_public_address(address: ipaddress._BaseAddress) -> bool:
    """排除私网、回环、链路本地、保留地址等不可由接口访问的地址。"""
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
