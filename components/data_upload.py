"""文件上传和LLM列分类组件"""
import json
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from config import UPLOADS_DIR
from db.crud import save_uploaded_file, update_file_classification
from llm.data_classifier import classify_dataframe

COLUMN_TYPE_OPTIONS = [
    "identifier",
    "date",
    "core_factor",
    "return",
    "rf",
    "market_factor",
    "control_var",
    "raw_text",
    "raw_score",
    "other",
]

TYPE_LABELS = {
    "identifier": "个体标识符（股票代码等）",
    "date": "时间/日期",
    "core_factor": "核心因子（解释变量）",
    "return": "收益率",
    "rf": "无风险收益率",
    "market_factor": "市场因子（MKT/SMB/HML等）",
    "control_var": "控制变量（市值/BM/动量等）",
    "raw_text": "原始文本",
    "raw_score": "原始打分",
    "other": "其他",
}


def render_upload_step(session_id: int, user_hint: str = "") -> dict | None:
    """
    渲染数据上传步骤。

    Returns
    -------
    dict | None — 已完成的列分类结果，或 None（尚未完成）
    """
    st.subheader("📂 第一步：上传你的数据")
    st.info("支持 .xlsx 或 .csv 格式。上传后AI将自动识别每列的含义，你也可以手动修正。")

    uploaded_file = st.file_uploader(
        "拖拽或点击上传数据文件",
        type=["xlsx", "csv"],
        key="data_uploader",
    )

    if uploaded_file is None:
        st.markdown("---")
        st.markdown("**还没有数据文件？** 可以先上传任意包含你研究核心变量的表格，格式不限。")
        return None

    # 读取文件
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"文件读取失败：{e}")
        return None

    st.success(f"成功读取 **{uploaded_file.name}**：{df.shape[0]} 行 × {df.shape[1]} 列")

    with st.expander("预览数据（前5行）", expanded=True):
        st.dataframe(df.head(), use_container_width=True)

    # 补充说明
    hint = st.text_area(
        "（可选）对你的数据作简要说明，帮助AI更准确地识别",
        placeholder="例如：这是上市公司每季度的投资者问答情绪打分数据，-1表示消极，+1表示积极...",
        value=user_hint,
        height=80,
    )

    classify_btn = st.button("🤖 AI自动识别列含义", type="primary", use_container_width=True)

    classification = st.session_state.get(f"classification_{session_id}")

    if classify_btn or classification is None and uploaded_file:
        with st.spinner("AI正在分析你的数据..."):
            classification = classify_dataframe(df, hint)
            st.session_state[f"classification_{session_id}"] = classification

    if classification is None:
        return None

    # ── 展示并允许修正分类结果 ────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🏷️ AI识别结果（可手动修正）")
    st.info(classification.get("data_summary", ""))

    columns_info = classification.get("columns", {})
    corrected = {}
    for col_name, info in columns_info.items():
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{col_name}**  \n_{info.get('desc', '')}_")
        with col2:
            current_type = info.get("type", "other")
            new_type = st.selectbox(
                "列类型",
                options=COLUMN_TYPE_OPTIONS,
                index=COLUMN_TYPE_OPTIONS.index(current_type) if current_type in COLUMN_TYPE_OPTIONS else 0,
                format_func=lambda x: TYPE_LABELS.get(x, x),
                key=f"col_{session_id}_{col_name}",
                label_visibility="collapsed",
            )
            corrected[col_name] = {"type": new_type, "desc": info.get("desc", "")}

    classification["columns"] = corrected

    # 因子构造建议
    suggestions = classification.get("factor_suggestions", [])
    if suggestions:
        st.markdown("---")
        st.subheader("💡 因子构造建议")
        for s in suggestions:
            st.markdown(f"- {s}")

    # 缺失数据提示
    missing = classification.get("missing_data", [])
    if missing:
        st.markdown("---")
        st.subheader("⚠️ 还缺少以下数据")
        for m in missing:
            st.warning(m)

    # 保存文件和分类结果
    confirm = st.button("✅ 确认列分类，进入下一步", type="primary", use_container_width=True)
    if confirm:
        # 保存上传文件到磁盘
        file_id = str(uuid.uuid4())[:8]
        save_path = UPLOADS_DIR / f"{session_id}_{file_id}_{uploaded_file.name}"
        if uploaded_file.name.endswith(".csv"):
            df.to_csv(save_path, index=False, encoding="utf-8-sig")
        else:
            df.to_excel(save_path, index=False)

        col_info = {col: {"dtype": str(df[col].dtype)} for col in df.columns}
        file_db_id = save_uploaded_file(session_id, uploaded_file.name, str(save_path),
                                         col_info, corrected)
        update_file_classification(file_db_id, corrected)

        st.session_state[f"uploaded_df_{session_id}"] = df
        st.session_state[f"confirmed_classification_{session_id}"] = corrected
        st.success("数据已保存！")
        return classification

    return None
