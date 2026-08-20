from __future__ import annotations

import base64
import binascii
import ipaddress
import socket
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, UnidentifiedImageError

from .settings import get_settings


ALLOWED_FILE_CONTENT_TYPES = {
    "application/octet-stream",
    "application/pdf",
    "image/bmp",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}

IMAGE_FORMATS = {
    "BMP": ("image/bmp", ".bmp"),
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


class FileInputError(ValueError):
    """The request file input is missing or invalid."""


class FileDownloadError(RuntimeError):
    """The public file URL is valid, but downloading failed."""


@dataclass(frozen=True)
class UploadedFile:
    name: str
    data: bytes
    content_type: str
    suffix: str


def decode_base64_file(value: str, *, name: str | None = None) -> UploadedFile:
    raw, declared_content_type = _split_data_url(value)
    if not raw:
        raise FileInputError("文件 Base64 为空")
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise FileInputError("文件 Base64 格式不正确") from exc
    return build_uploaded_file(data, content_type=declared_content_type, name=name)


def build_uploaded_file(
    data: bytes,
    *,
    content_type: str | None = None,
    name: str | None = None,
) -> UploadedFile:
    if not data or len(data) > get_settings().max_file_bytes:
        raise FileInputError("文件大小不合法")

    normalized_content_type = _normalize_content_type(content_type)
    if normalized_content_type and normalized_content_type not in ALLOWED_FILE_CONTENT_TYPES:
        raise FileInputError("文件 Content-Type 不受支持")

    detected_content_type, suffix = _detect_file_type(data)
    if (
        normalized_content_type
        and normalized_content_type != "application/octet-stream"
        and normalized_content_type != detected_content_type
        and not (normalized_content_type == "image/jpg" and detected_content_type == "image/jpeg")
    ):
        raise FileInputError("文件 Content-Type 与内容不一致")

    file_name = _safe_upload_name(name, suffix)
    return UploadedFile(
        name=file_name,
        data=data,
        content_type=detected_content_type,
        suffix=suffix,
    )


@contextmanager
def materialize_file(uploaded: UploadedFile) -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / uploaded.name
        path.write_bytes(uploaded.data)
        yield path


async def load_request_file(
    file: str | None,
    file_type: int | None = None,
) -> UploadedFile:
    if not file or not file.strip():
        raise FileInputError("缺少文件来源")

    source = file.strip()
    if source.lower().startswith(("http://", "https://")):
        uploaded = await load_file_from_url(source)
    else:
        uploaded = decode_base64_file(source)

    _validate_file_type(uploaded, file_type)
    return uploaded


def infer_serving_file_type(uploaded: UploadedFile) -> int:
    if uploaded.content_type == "application/pdf":
        return 0
    if uploaded.content_type.startswith("image/"):
        return 1
    raise FileInputError("文件类型不受支持")


def _validate_file_type(uploaded: UploadedFile, file_type: int | None) -> None:
    if file_type is None:
        return
    if file_type not in {0, 1}:
        raise FileInputError("fileType 只支持 0 或 1")
    actual_file_type = infer_serving_file_type(uploaded)
    if actual_file_type != file_type:
        raise FileInputError("fileType 与文件内容不一致")


def validate_public_file_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise FileInputError("文件 URL 不合法")
    if parsed.username or parsed.password:
        raise FileInputError("文件 URL 不允许包含用户名或密码")

    for address in _resolve_host(parsed.hostname):
        if not _is_public_address(address):
            raise FileInputError("non-public file url")
    return parsed.geturl()


async def load_file_from_url(url: str) -> UploadedFile:
    current_url = validate_public_file_url(url)
    async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
        for _ in range(4):
            try:
                response = await client.get(current_url)
            except httpx.HTTPError as exc:
                raise FileDownloadError("文件下载失败") from exc

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise FileDownloadError("文件 URL 重定向不合法")
                current_url = validate_public_file_url(str(response.url.join(location)))
                continue

            if response.status_code >= 400:
                raise FileDownloadError(f"文件下载失败，HTTP 状态码：{response.status_code}")

            content_type = _normalize_content_type(response.headers.get("content-type"))
            content = response.content
            if len(content) > get_settings().max_file_bytes:
                raise FileInputError("文件超过大小限制")
            name = Path(urlparse(str(response.url)).path).name or None
            return build_uploaded_file(content, content_type=content_type, name=name)
    raise FileDownloadError("文件 URL 重定向次数过多")


def _split_data_url(value: str) -> tuple[str, str | None]:
    raw = (value or "").strip()
    if not raw:
        return "", None
    if not raw.lower().startswith("data:"):
        return raw, None
    if "," not in raw:
        raise FileInputError("data URL 格式不正确")
    header, payload = raw.split(",", 1)
    if ";base64" not in header.lower():
        raise FileInputError("data URL 必须使用 Base64")
    content_type = header[5:].split(";", 1)[0] or None
    return payload, _normalize_content_type(content_type)


def _detect_file_type(data: bytes) -> tuple[str, str]:
    if data.lstrip().startswith(b"%PDF"):
        return "application/pdf", ".pdf"

    try:
        image = Image.open(BytesIO(data))
        image.verify()
        image_format = image.format
    except (UnidentifiedImageError, OSError) as exc:
        raise FileInputError("文件内容无法识别") from exc

    if image_format not in IMAGE_FORMATS:
        raise FileInputError("图片格式不受支持")
    return IMAGE_FORMATS[image_format]


def _safe_upload_name(name: str | None, suffix: str) -> str:
    if not name:
        return f"upload{suffix}"
    stem = Path(name).stem.strip() or "upload"
    safe_stem = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in stem)
    return f"{safe_stem}{suffix}"


def _normalize_content_type(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.split(";", 1)[0].strip().lower()
    return value or None


def _resolve_host(hostname: str) -> Iterable[ipaddress._BaseAddress]:
    try:
        return [
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        ]
    except (socket.gaierror, ValueError) as exc:
        raise FileInputError("文件 URL 域名无法解析") from exc


def _is_public_address(address: ipaddress._BaseAddress) -> bool:
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
