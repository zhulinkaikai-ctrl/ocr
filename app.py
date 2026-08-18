from __future__ import annotations

import streamlit as st
from PIL import Image, UnidentifiedImageError

from ocr_api.env_loader import load_env_file

load_env_file()

from id_card_ocr.paddle_adapter import PaddleOCRUnavailableError
from id_card_ocr.paddleocr_vl_adapter import PaddleOCRVLAdapter


@st.cache_resource(show_spinner=False)
def get_ocr_adapter() -> PaddleOCRVLAdapter:
    # PaddleOCR-VL-1.6 模型初始化比较慢，所以 Streamlit 会缓存这个对象。
    # 用户多次上传图片时不会重复加载模型，体验会快很多。
    return PaddleOCRVLAdapter(enable_orientation=True)


def main() -> None:
    st.set_page_config(page_title="OCR 识别 Demo", layout="wide")
    _inject_styles()

    st.title("OCR 识别 Demo")
    st.caption("上传身份证或营业执照图片，查看 PaddleOCR-VL 原始 JSON；不保存上传文件。")

    uploaded_file = st.file_uploader(
        "上传图片",
        type=["jpg", "jpeg", "png", "bmp", "webp"],
        accept_multiple_files=False,
    )

    if uploaded_file is None:
        st.info("请选择一张身份证或营业执照图片。")
        return

    try:
        image = Image.open(uploaded_file).convert("RGB")
    except UnidentifiedImageError:
        st.error("图片无法读取，请换一张清晰图片。")
        return

    preview_col, result_col = st.columns([0.95, 1.05], gap="large")
    with preview_col:
        st.subheader("图片预览")
        st.image(image, width="stretch")

    with result_col:
        st.subheader("PaddleOCR-VL 原始 JSON")
        if st.button("开始识别", type="primary", width="stretch"):
            result = _run_ocr(image)
            if result is not None:
                st.json(result)


def _run_ocr(image: Image.Image):
    adapter = get_ocr_adapter()
    try:
        with st.spinner("正在识别"):
            return adapter.recognize(image)
    except PaddleOCRUnavailableError as exc:
        st.error(str(exc))
        return None
    except Exception as exc:
        st.error(f"OCR 识别失败：{exc}")
        return None


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
