from __future__ import annotations

import json
from collections import Counter
from typing import Any, Literal

import streamlit as st
from PIL import Image, UnidentifiedImageError

from id_card_ocr.business_license import extract_business_license
from id_card_ocr.extractor import extract_id_card
from id_card_ocr.models import IDCardResult, OCRLine
from id_card_ocr.paddle_adapter import PaddleOCRAdapter, PaddleOCRUnavailableError
from ocr_api.responses import build_business_license_success, build_id_card_success


DocumentType = Literal["身份证", "营业执照"]


@st.cache_resource(show_spinner=False)
def get_ocr_adapter() -> PaddleOCRAdapter:
    return PaddleOCRAdapter(lang="ch", enable_orientation=True)


def main() -> None:
    st.set_page_config(page_title="OCR 识别 Demo", layout="wide")
    _inject_styles()

    st.title("OCR 识别 Demo")
    st.caption("本地运行 · 支持身份证和营业执照 · 不保存上传文件")

    id_card_tab, business_license_tab = st.tabs(["身份证", "营业执照"])

    with id_card_tab:
        _render_document_panel(
            document_type="身份证",
            uploader_label="上传身份证图片",
            empty_text="请选择一张身份证正面或反面图片。",
            button_label="识别身份证",
        )

    with business_license_tab:
        _render_document_panel(
            document_type="营业执照",
            uploader_label="上传营业执照图片",
            empty_text="请选择一张营业执照图片。",
            button_label="识别营业执照",
        )


def _render_document_panel(
    document_type: DocumentType,
    uploader_label: str,
    empty_text: str,
    button_label: str,
) -> None:
    uploaded_file = st.file_uploader(
        uploader_label,
        type=["jpg", "jpeg", "png", "bmp", "webp"],
        accept_multiple_files=False,
        key=f"{document_type}-upload",
    )

    if uploaded_file is None:
        st.info(empty_text)
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
        if st.button(button_label, type="primary", use_container_width=True, key=f"{document_type}-button"):
            result = _run_ocr(document_type, image)
            if result is not None:
                _render_result(document_type, result)


def _run_ocr(document_type: DocumentType, image: Image.Image) -> dict[str, Any] | None:
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

    return build_demo_document_result(document_type, lines)


def build_demo_document_result(document_type: DocumentType, lines: list[OCRLine]) -> dict[str, Any]:
    if document_type == "身份证":
        result = extract_id_card(lines)
        payload = build_id_card_success("LOCAL-DEMO", result)
        payload["data"]["raw_texts"] = result.raw_texts
        payload["data"]["detail"] = result.to_json_dict()
        return payload

    content = extract_business_license(lines)
    payload = build_business_license_success("LOCAL-DEMO", content)
    payload["data"]["raw_texts"] = [line.text for line in lines]
    return payload


def _render_result(document_type: DocumentType, payload: dict[str, Any]) -> None:
    if document_type == "身份证":
        _render_id_card_summary(payload)
    else:
        _render_business_license_summary(payload)

    st.subheader("JSON")
    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")

    with st.expander("原始 OCR 文本"):
        raw_texts = payload.get("data", {}).get("raw_texts", [])
        if raw_texts:
            st.write("\n".join(raw_texts))
        else:
            st.write("无")


def _render_id_card_summary(payload: dict[str, Any]) -> None:
    data = payload.get("data", {})
    detail = data.get("detail", {})
    fields = detail.get("字段", [])
    status_counts = Counter(field.get("status") for field in fields)

    doc_col, ok_col, miss_col, warn_col = st.columns(4)
    doc_col.metric("证件面", detail.get("证件面", "未知"))
    ok_col.metric("通过", status_counts.get("通过", 0))
    miss_col.metric("缺失", status_counts.get("缺失", 0))
    warn_col.metric("疑似错误", status_counts.get("疑似错误", 0))

    table_rows = [
        {
            "字段": field.get("label", ""),
            "值": field.get("value", ""),
            "状态": field.get("status", ""),
            "置信度": _format_confidence(field.get("confidence")),
        }
        for field in fields
    ]
    st.dataframe(table_rows, hide_index=True, use_container_width=True)


def _render_business_license_summary(payload: dict[str, Any]) -> None:
    content = payload.get("data", {}).get("content", {})
    summary_rows = [
        {"字段": "统一社会信用代码", "值": content.get("credit_code", "")},
        {"字段": "注册号", "值": content.get("registration_code", "")},
        {"字段": "企业名称", "值": content.get("enterprise_name", "")},
        {"字段": "企业类型", "值": content.get("enterprise_type", "")},
        {"字段": "法人（或经营者）姓名", "值": content.get("lR_name", "")},
        {"字段": "注册资本", "值": content.get("registration_capital", "")},
        {"字段": "成立时间", "值": content.get("establishing_date", "")},
        {"字段": "经营期限", "值": content.get("op_period", "")},
        {"字段": "经营日期开始", "值": content.get("op_from", "")},
        {"字段": "经营日期结束", "值": content.get("op_to", "")},
        {"字段": "地址（或经营场所）", "值": content.get("address", "")},
        {"字段": "组成形式", "值": content.get("org_form", "")},
        {"字段": "是否复印件", "值": content.get("is_copy", "")},
    ]
    st.dataframe(summary_rows, hide_index=True, use_container_width=True)

    op_scope = content.get("op_scope")
    if op_scope:
        st.text_area("经营范围", value=str(op_scope), height=140, disabled=True)


def _format_confidence(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.2%}"


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
