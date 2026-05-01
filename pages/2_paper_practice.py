"""论文实践操盘页面"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pandas as pd
import streamlit as st

from db.database import init_db
from db.crud import (
    get_sessions, create_session, get_session, update_session_state,
    get_analysis_results, get_chat_history, add_chat_message,
    toggle_in_paper, get_uploaded_files,
)
from components.chat_interface import render_chat_history, get_user_input, stream_assistant_response
from components.data_upload import render_upload_step
from components.analysis_hub import render_analysis_hub
from components.result_display import display_summary_table, export_results_to_excel
from llm.research_advisor import stream_research_advice, suggest_paper_framework, extract_research_plan

init_db()

st.set_page_config(
    page_title="论文实践 | QuantResearch",
    page_icon="📝",
    layout="wide",
)

# ── 登录检查 ────────────────────────────────────────────────────────────────
if "user_id" not in st.session_state:
    st.warning("请先在主页登录")
    st.page_link("app.py", label="返回主页")
    st.stop()

user_id = st.session_state["user_id"]
username = st.session_state.get("username", "用户")

# ── 侧边栏 ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"👋 **{username}**")
    if st.button("🏠 返回主页", use_container_width=True):
        st.switch_page("app.py")

    st.markdown("---")
    st.markdown("### 📁 我的研究会话")

    sessions = get_sessions(user_id)
    practice_sessions = [s for s in sessions if s["mode"] == "practice"]

    if st.button("➕ 新建研究项目", type="primary", use_container_width=True):
        sid = create_session(user_id, f"研究项目_{len(practice_sessions)+1}", "practice")
        st.session_state["practice_session_id"] = sid
        st.rerun()

    for s in practice_sessions[:8]:
        label = s["session_name"][:18] + ("..." if len(s["session_name"]) > 18 else "")
        if st.button(f"📝 {label}", key=f"ps_{s['id']}", use_container_width=True):
            st.session_state["practice_session_id"] = s["id"]
            st.rerun()

    st.markdown("---")
    st.markdown("### 📋 已有代码库")
    code_sections = {
        "单变量排序": "quant/univariate_sort.py",
        "FM截面回归": "quant/fm_regression.py",
        "独立双排序": "quant/double_sort.py",
        "条件双排序": "quant/double_sort.py",
        "CAPM/FF3/FF5": "quant/factor_models.py",
        "数据预处理": "quant/preprocessing.py",
    }
    selected_code = st.selectbox("查看代码", list(code_sections.keys()))
    code_path = Path(__file__).parent.parent / code_sections[selected_code]
    if code_path.exists():
        with st.expander("查看代码", expanded=False):
            st.code(code_path.read_text(encoding="utf-8"), language="python")

# ── 确保有活跃会话 ───────────────────────────────────────────────────────────
if "practice_session_id" not in st.session_state:
    sessions = get_sessions(user_id)
    practice_sessions = [s for s in sessions if s["mode"] == "practice"]
    if practice_sessions:
        st.session_state["practice_session_id"] = practice_sessions[0]["id"]
    else:
        sid = create_session(user_id, "研究项目_1", "practice")
        st.session_state["practice_session_id"] = sid

session_id = st.session_state["practice_session_id"]
session_data = get_session(session_id)
state = json.loads(session_data.get("state_json", "{}")) if session_data else {}

st.title(f"📝 {session_data.get('session_name', '论文实践') if session_data else '论文实践'}")

# ── 四步骤进度条 ──────────────────────────────────────────────────────────────
step = state.get("step", 1)
step_names = ["① 数据上传与识别", "② 论文框架商讨", "③ 回归分析", "④ 结果汇总与导出"]
cols_progress = st.columns(4)
for i, name in enumerate(step_names):
    with cols_progress[i]:
        if i + 1 < step:
            st.markdown(f"<div style='text-align:center; color:#28a745;'>✅ {name}</div>", unsafe_allow_html=True)
        elif i + 1 == step:
            st.markdown(f"<div style='text-align:center; color:#007bff; font-weight:bold;'>🔵 {name}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align:center; color:#aaa;'>⚪ {name}</div>", unsafe_allow_html=True)

st.markdown("---")

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1: 数据上传
# ──────────────────────────────────────────────────────────────────────────────
if step == 1:
    classification = render_upload_step(session_id)
    if classification is not None:
        state["step"] = 2
        state["classification"] = json.loads(json.dumps(classification, ensure_ascii=False))
        update_session_state(session_id, state)
        st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2: 论文框架商讨
# ──────────────────────────────────────────────────────────────────────────────
elif step == 2:
    st.subheader("💬 第二步：论文框架商讨")
    classification = state.get("classification", {})
    data_summary = classification.get("data_summary", "")

    if not state.get("framework_generated"):
        with st.spinner("AI正在为你生成论文框架建议..."):
            framework = suggest_paper_framework(classification)
        state["framework_generated"] = True
        state["framework_text"] = framework
        update_session_state(session_id, state)

    framework_text = state.get("framework_text", "")
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(framework_text)

    st.markdown("---")
    st.markdown("### 与AI老师讨论你的研究方向")
    history = get_chat_history(session_id, limit=20)
    render_chat_history([h for h in history if h.get("content") != framework_text])

    user_input = get_user_input("问一问：我的数据可以研究什么问题？应该用哪些控制变量？...")
    if user_input:
        add_chat_message(session_id, "user", user_input)
        with st.chat_message("assistant", avatar="🤖"):
            ph = st.empty()
            reply = ""
            for chunk in stream_research_advice(
                user_input, history, data_summary=data_summary, paper_stage="framework"
            ):
                reply += chunk
                ph.markdown(reply + "▌")
            ph.markdown(reply)
        add_chat_message(session_id, "assistant", reply)
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ 返回上传数据", use_container_width=True):
            state["step"] = 1
            update_session_state(session_id, state)
            st.rerun()
    with col2:
        if st.button("进入回归分析 ➡️", type="primary", use_container_width=True):
            with st.spinner("AI正在整理你的研究计划..."):
                full_history = get_chat_history(session_id, limit=30)
                plan = extract_research_plan(full_history, classification)
            state["research_plan"] = plan
            state["step"] = 3
            update_session_state(session_id, state)
            st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# STEP 3: 回归分析
# ──────────────────────────────────────────────────────────────────────────────
elif step == 3:
    classification = state.get("classification", {})
    col_classification = classification.get("columns", {})

    # 加载已上传的DataFrame
    df_key = f"uploaded_df_{session_id}"
    if df_key not in st.session_state:
        files = get_uploaded_files(session_id)
        if files:
            latest = files[-1]
            try:
                fpath = latest["file_path"]
                if fpath.endswith(".csv"):
                    st.session_state[df_key] = pd.read_csv(fpath)
                else:
                    st.session_state[df_key] = pd.read_excel(fpath)
            except Exception as e:
                st.error(f"加载数据失败：{e}")
                st.stop()
        else:
            st.warning("未找到上传数据，请返回第一步重新上传")
            if st.button("返回第一步"):
                state["step"] = 1
                update_session_state(session_id, state)
                st.rerun()
            st.stop()

    df = st.session_state[df_key]
    render_analysis_hub(session_id, df, col_classification,
                        research_plan=state.get("research_plan"))

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ 返回框架商讨", use_container_width=True):
            state["step"] = 2
            update_session_state(session_id, state)
            st.rerun()
    with col2:
        if st.button("查看结果汇总 ➡️", type="primary", use_container_width=True):
            state["step"] = 4
            update_session_state(session_id, state)
            st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# STEP 4: 结果汇总与导出
# ──────────────────────────────────────────────────────────────────────────────
elif step == 4:
    st.subheader("📊 第四步：结果汇总与导出")
    results = get_analysis_results(session_id)

    if not results:
        st.info("暂无分析结果，请先在第三步运行分析。")
    else:
        for res in results:
            with st.expander(f"{res['analysis_type']} — {res['created_at'][:16]}", expanded=False):
                col1, col2 = st.columns([4, 1])
                with col1:
                    if res.get("interpretation"):
                        st.markdown(res["interpretation"])
                with col2:
                    in_paper = bool(res.get("in_paper"))
                    new_val = st.checkbox("加入论文", value=in_paper, key=f"paper_{res['id']}")
                    if new_val != in_paper:
                        toggle_in_paper(res["id"], new_val)
                        st.rerun()

        # 导出
        paper_results = [r for r in results if r.get("in_paper")]
        st.markdown(f"### 已选择 {len(paper_results)} 个结果加入论文")

        if paper_results:
            excel_bytes = export_results_to_excel(paper_results)
            st.download_button(
                label="⬇️ 下载选中结果（Excel）",
                data=excel_bytes,
                file_name=f"quant_results_{session_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ 继续做分析", use_container_width=True):
            state["step"] = 3
            update_session_state(session_id, state)
            st.rerun()
    with col2:
        if st.button("💬 咨询AI老师", use_container_width=True):
            state["step"] = 2
            update_session_state(session_id, state)
            st.rerun()
