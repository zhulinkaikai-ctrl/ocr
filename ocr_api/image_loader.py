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


MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/bmp",
    "image/webp",
}


class ImageInputError(ValueError):
    pass


class ImageDownloadError(RuntimeError):
    pass


def decode_base64_image(value: str) -> Image.Image:
    raw = (value or "").strip()
    if not raw:
        raise ImageInputError("empty base64 image")
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageInputError("invalid base64 image") from exc
    return decode_image_bytes(data)


def decode_image_bytes(data: bytes) -> Image.Image:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ImageInputError("invalid image size")
    try:
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
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ImageInputError("invalid image url")
    if parsed.username or parsed.password:
        raise ImageInputError("invalid image url")

    for address in _resolve_host(parsed.hostname):
        if not _is_public_address(address):
            raise ImageInputError("non-public image url")
    return parsed.geturl()


async def load_image_from_url(url: str) -> Image.Image:
    current_url = validate_public_image_url(url)
    async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
        for _ in range(4):
            try:
                response = await client.get(current_url)
            except httpx.HTTPError as exc:
                raise ImageDownloadError("failed to download image") from exc
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise ImageDownloadError("invalid redirect")
                current_url = validate_public_image_url(str(response.url.join(location)))
                continue

            if response.status_code >= 400:
                raise ImageDownloadError(f"download failed with status {response.status_code}")
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
                raise ImageInputError("invalid image content type")
            content = response.content
            if len(content) > MAX_IMAGE_BYTES:
                raise ImageInputError("image too large")
            return decode_image_bytes(content)
    raise ImageDownloadError("too many redirects")


async def load_request_image(image_base64: str | None, image_url: str | None) -> Image.Image:
    if image_base64 and image_base64.strip():
        return decode_base64_image(image_base64)
    if image_url and image_url.strip():
        return await load_image_from_url(image_url)
    raise ImageInputError("missing image source")


def _resolve_host(hostname: str) -> Iterable[ipaddress._BaseAddress]:
    try:
        return [
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        ]
    except (socket.gaierror, ValueError) as exc:
        raise ImageInputError("invalid image url host") from exc


def _is_public_address(address: ipaddress._BaseAddress) -> bool:
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
