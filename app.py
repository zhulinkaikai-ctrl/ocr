from __future__ import annotations

import json
from io import BytesIO
from typing import Any

import streamlit as st
from PIL import Image, UnidentifiedImageError

from ocr_api.adapter import (
    PPStructureV3Adapter,
    PPStructureV3UnavailableError,
    collapse_raw_results,
)
from ocr_api.file_loader import (
    FileInputError,
    UploadedFile,
    build_uploaded_file,
    materialize_file,
)


SUPPORTED_UPLOAD_TYPES = ["jpg", "jpeg", "png", "bmp", "webp", "pdf"]


@st.cache_resource(show_spinner=False)
def get_ocr_adapter() -> PPStructureV3Adapter:
    return PPStructureV3Adapter(lang="ch", enable_orientation=True)


def main() -> None:
    st.set_page_config(page_title="PP-StructureV3 OCR", layout="wide")
    _inject_styles()

    st.title("PP-StructureV3 OCR")

    uploaded_file = st.file_uploader(
        "上传文件",
        type=SUPPORTED_UPLOAD_TYPES,
        accept_multiple_files=False,
    )
    if uploaded_file is None:
        st.info("请选择图片或 PDF。")
        return

    try:
        uploaded = build_uploaded_file(
            uploaded_file.getvalue(),
            content_type=uploaded_file.type,
            name=uploaded_file.name,
        )
    except FileInputError as exc:
        st.error(str(exc))
        return

    preview_col, result_col = st.columns([0.95, 1.05], gap="large")
    with preview_col:
        _render_preview(uploaded)

    with result_col:
        st.subheader("识别结果")
        if st.button("识别", type="primary", use_container_width=True):
            payload = _run_ocr(uploaded)
            if payload is not None:
                _render_result(payload)


def build_display_payload(results: list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]]:
    return collapse_raw_results(results)


def _run_ocr(uploaded: UploadedFile) -> dict[str, Any] | list[dict[str, Any]] | None:
    try:
        with st.spinner("正在识别"):
            with materialize_file(uploaded) as input_path:
                results = get_ocr_adapter().recognize(input_path)
    except PPStructureV3UnavailableError as exc:
        st.error(str(exc))
        return None
    except Exception as exc:
        st.error(f"OCR 识别失败：{exc}")
        return None
    return build_display_payload(results)


def _render_preview(uploaded: UploadedFile) -> None:
    st.subheader("文件预览")
    if uploaded.content_type.startswith("image/"):
        try:
            image = Image.open(BytesIO(uploaded.data)).convert("RGB")
        except UnidentifiedImageError:
            st.error("图片无法读取，请换一个文件。")
            return
        st.image(image, use_container_width=True)
        return

    st.metric("格式", uploaded.suffix.upper().lstrip("."))
    st.metric("大小", _format_size(len(uploaded.data)))
    st.write(uploaded.name)


def _render_result(payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    st.subheader("原始 JSON")
    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1180px;
            padding-top: 2.2rem;
            padding-bottom: 2.5rem;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        div[data-testid="stMetric"] {
            border: 1px solid #d8dee8;
            border-radius: 8px;
            padding: 0.65rem 0.8rem;
            background: #fbfcfe;
        }
        div[data-testid="stFileUploader"] section {
            border-radius: 8px;
            border-color: #cbd5e1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
