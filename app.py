from __future__ import annotations

from typing import Any

import streamlit as st

from env_file import load_env_file
from ocr_client import OCRClient, OCRClientError
from ocr_settings import get_settings


load_env_file()


SUPPORTED_FILE_TYPES = ["jpg", "jpeg", "png", "bmp", "webp", "pdf"]
DOCUMENT_TYPES = ["身份证", "营业执照", "发票"]


@st.cache_resource(show_spinner=False)
def get_ocr_client() -> OCRClient:
    """复用本地 Docker OCR 服务的 HTTP 客户端。"""
    return OCRClient()


def main() -> None:
    st.set_page_config(page_title="PaddleOCR-VL 本地测试", layout="wide")
    settings = get_settings()

    st.title("PaddleOCR-VL 本地测试")
    st.caption(f"模型服务：{settings.ocr_service_url}")

    document_type = st.selectbox("识别类型", DOCUMENT_TYPES)
    uploaded_file = st.file_uploader(
        "上传图片或 PDF",
        type=SUPPORTED_FILE_TYPES,
        accept_multiple_files=False,
    )
    visualize = st.checkbox("返回可视化结果", value=False)

    if uploaded_file is None:
        st.info("请选择身份证、营业执照或发票图片/PDF。")
        return

    file_bytes = uploaded_file.getvalue()
    preview_col, result_col = st.columns([0.85, 1.15], gap="large")
    with preview_col:
        st.subheader("文件预览")
        if uploaded_file.name.lower().endswith(".pdf"):
            st.info(f"已选择 PDF：{uploaded_file.name}")
        else:
            st.image(file_bytes, width="stretch")

    with result_col:
        st.subheader(f"{document_type}识别结果")
        if st.button("开始识别", type="primary", width="stretch"):
            try:
                with st.spinner("正在调用本机 PaddleOCR-VL 服务"):
                    result = _run_ocr(
                        get_ocr_client(),
                        uploaded_file.name,
                        file_bytes,
                        visualize=visualize,
                    )
            except OCRClientError as exc:
                st.error(str(exc))
            else:
                st.json(result)


def _run_ocr(
    client: OCRClient,
    filename: str,
    file_bytes: bytes,
    *,
    visualize: bool,
) -> dict[str, Any]:
    """调用本机 Docker 服务，不解析或改写官方 JSON。"""
    return client.recognize(filename, file_bytes, visualize=visualize)


if __name__ == "__main__":
    main()
