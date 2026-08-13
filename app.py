from __future__ import annotations

import json
from collections import Counter

import streamlit as st
from PIL import Image, UnidentifiedImageError

from id_card_ocr.extractor import extract_id_card
from id_card_ocr.models import IDCardResult
from id_card_ocr.paddle_adapter import PaddleOCRAdapter, PaddleOCRUnavailableError


@st.cache_resource(show_spinner=False)
def get_ocr_adapter() -> PaddleOCRAdapter:
    return PaddleOCRAdapter(lang="ch", enable_orientation=True)


def main() -> None:
    st.set_page_config(page_title="身份证 OCR", layout="wide")
    _inject_styles()

    st.title("身份证 OCR")
    st.caption("本地运行 · 单张身份证图片 · 不保存上传文件")

    uploaded_file = st.file_uploader(
        "图片",
        type=["jpg", "jpeg", "png", "bmp", "webp"],
        accept_multiple_files=False,
    )

    if uploaded_file is None:
        st.info("请选择一张身份证正面或反面图片。")
        return

    try:
        image = Image.open(uploaded_file).convert("RGB")
    except UnidentifiedImageError:
        st.error("图片无法读取，请换一张清晰图片。")
        return

    preview_col, result_col = st.columns([0.95, 1.05], gap="large")
    with preview_col:
        st.subheader("图片预览")
        st.image(image, use_container_width=True)

    with result_col:
        st.subheader("识别结果")
        if st.button("开始识别", type="primary", use_container_width=True):
            result = _run_ocr(image)
            if result is not None:
                _render_result(result)


def _run_ocr(image: Image.Image) -> IDCardResult | None:
    try:
        with st.spinner("正在识别"):
            lines = get_ocr_adapter().recognize(image)
    except PaddleOCRUnavailableError as exc:
        st.error(str(exc))
        return None
    except Exception as exc:
        st.error(f"OCR 识别失败：{exc}")
        return None

    if not lines:
        st.warning("没有识别到文字。")

    return extract_id_card(lines)


def _render_result(result: IDCardResult) -> None:
    payload = result.to_json_dict()
    status_counts = Counter(field.status for field in result.fields)

    doc_col, ok_col, miss_col, warn_col = st.columns(4)
    doc_col.metric("证件面", result.side)
    ok_col.metric("通过", status_counts.get("通过", 0))
    miss_col.metric("缺失", status_counts.get("缺失", 0))
    warn_col.metric("疑似错误", status_counts.get("疑似错误", 0))

    table_rows = [
        {
            "字段": field.label,
            "值": field.value or "",
            "状态": field.status,
            "置信度": _format_confidence(field.confidence),
        }
        for field in result.fields
    ]
    st.dataframe(table_rows, hide_index=True, use_container_width=True)

    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    st.subheader("JSON")
    st.code(json_text, language="json")

    with st.expander("原始 OCR 文本"):
        if result.raw_texts:
            st.write("\n".join(result.raw_texts))
        else:
            st.write("无")


def _format_confidence(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2%}"


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
