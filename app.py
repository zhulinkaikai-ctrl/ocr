from __future__ import annotations

import json
from collections import Counter
from typing import Any, Literal

import streamlit as st
from PIL import Image, UnidentifiedImageError

from id_card_ocr.business_license import extract_business_license
from id_card_ocr.extractor import extract_id_card
from id_card_ocr.models import IDCardResult, OCRLine
from id_card_ocr.paddle_adapter import PaddleOCRUnavailableError
from id_card_ocr.paddleocr_vl_adapter import PaddleOCRVLAdapter
from ocr_api.responses import build_business_license_success, build_id_card_success


# 页面里只允许这两种证件类型。用 Literal 的好处是：后面 IDE/类型检查能提醒拼写错误。
DocumentType = Literal["身份证", "营业执照"]


@st.cache_resource(show_spinner=False)
def get_ocr_adapter() -> PaddleOCRVLAdapter:
    # PaddleOCR-VL-1.6 模型初始化比较慢，所以 Streamlit 会缓存这个对象。
    # 用户多次上传图片时不会重复加载模型，体验会快很多。
    return PaddleOCRVLAdapter(enable_orientation=True)


def main() -> None:
    # main 是本地调试页面入口：这里只负责页面布局，不直接写识别规则。
    # 真正的 OCR 识别在 PaddleOCRVLAdapter，字段提取在 extractor/business_license。
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
    # 身份证和营业执照的上传交互基本一样，所以复用这一个面板函数。
    # document_type 决定后续走哪个字段抽取器。
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
        # 统一转成 RGB，是为了让 PaddleOCR-VL 后面拿到稳定的 3 通道图片。
        # PNG 透明通道、灰度图等格式在这里都会被归一化。
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
            # 这里拿到的是 OCR 原始文本行，还不是身份证/营业执照字段。
            # 字段结构化在 build_demo_document_result 里根据 document_type 分流。
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
    # 本地页面展示的 JSON 尽量复用 API 返回格式，方便你边上传调试边对照接口合同。
    # LOCAL-DEMO 只是页面调试用的订单号；正式 API 会用请求里的 orderNo 或自动生成。
    if document_type == "身份证":
        result = extract_id_card(lines)
        payload = build_id_card_success("LOCAL-DEMO", result)
        # API 返回里默认不带调试细节；页面为了方便排查，多附加原始文本和内部字段明细。
        payload["data"]["raw_texts"] = result.raw_texts
        payload["data"]["detail"] = result.to_json_dict()
        return payload

    content = extract_business_license(lines)
    payload = build_business_license_success("LOCAL-DEMO", content)
    payload["data"]["raw_texts"] = [line.text for line in lines]
    return payload


def _render_result(document_type: DocumentType, payload: dict[str, Any]) -> None:
    # 先给人看的摘要表，再给机器看的完整 JSON。
    # 这样你可以快速扫结果，也可以直接复制 JSON 去和外部调用方确认格式。
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
    # 身份证字段带校验状态，所以摘要里额外统计“通过/缺失/疑似错误”。
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
    # 营业执照没有逐字段置信度和校验状态，页面直接按你确认的 API 字段顺序展示。
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
