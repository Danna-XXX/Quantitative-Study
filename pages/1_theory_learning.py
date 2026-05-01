"""理论学习模式页面"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from db.database import init_db
from db.crud import (
    get_sessions, create_session, get_chat_history,
    add_chat_message, get_session,
)
from components.chat_interface import render_chat_history, get_user_input, stream_assistant_response
from components.data_upload import render_upload_step
from llm.theory_tutor import stream_theory_answer, analyze_uploaded_data_proactively
from config import KNOWLEDGE_DIR

init_db()

st.set_page_config(page_title="理论学习 | QuantResearch", page_icon="📚", layout="wide")

# ── 登录检查 ────────────────────────────────────────────────────────────────
if "user_id" not in st.session_state:
    st.warning("请先在主页登录")
    st.page_link("app.py", label="返回主页")
    st.stop()

user_id = st.session_state["user_id"]
username = st.session_state.get("username", "用户")

# ── 侧边栏：理论模块 + 会话 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"👋 **{username}**")
    if st.button("🏠 返回主页", use_container_width=True):
        st.switch_page("app.py")

    st.markdown("---")
    st.markdown("### 📚 理论知识模块")

    topics = {
        "🔬 因子基础理论": "factor_basics.md",
        "📊 组合排序方法": "portfolio_sorting.md",
        "📈 FM截面回归": "fm_regression.md",
        "🏛️ 因子模型(CAPM/FF3/FF5)": "factor_models.md",
        "🗄️ 数据来源指南": "data_sources.md",
    }

    selected_topic = st.radio("选择知识模块", list(topics.keys()),
                               label_visibility="collapsed")
    topic_file = topics[selected_topic]

    st.markdown("---")
    st.markdown("### 💬 对话历史")
    sessions = get_sessions(user_id)
    theory_sessions = [s for s in sessions if s["mode"] == "theory"]

    if st.button("➕ 新建理论学习会话", use_container_width=True):
        sid = create_session(user_id, f"理论学习_{len(theory_sessions)+1}", "theory")
        st.session_state["theory_session_id"] = sid
        st.rerun()

    for s in theory_sessions[:5]:
        if st.button(f"📝 {s['session_name'][:20]}", key=f"ts_{s['id']}", use_container_width=True):
            st.session_state["theory_session_id"] = s["id"]
            st.rerun()

# ── 主内容区 ────────────────────────────────────────────────────────────────
st.title("📚 理论学习")
st.markdown("和AI老师讨论量化金融理论，也可以上传数据让AI主动分析。")

# 确保有活跃会话
if "theory_session_id" not in st.session_state:
    sessions = get_sessions(user_id)
    theory_sessions = [s for s in sessions if s["mode"] == "theory"]
    if theory_sessions:
        st.session_state["theory_session_id"] = theory_sessions[0]["id"]
    else:
        sid = create_session(user_id, "理论学习_1", "theory")
        st.session_state["theory_session_id"] = sid

session_id = st.session_state["theory_session_id"]

tab_chat, tab_knowledge, tab_upload = st.tabs(["💬 AI对话", "📖 知识库", "📂 上传数据分析"])

# ── Tab1：AI对话 ─────────────────────────────────────────────────────────────
with tab_chat:
    history = get_chat_history(session_id, limit=30)
    render_chat_history(history)

    user_input = get_user_input("输入你的量化理论问题...")
    if user_input:
        add_chat_message(session_id, "user", user_input)
        with st.chat_message("assistant", avatar="🤖"):
            placeholder = st.empty()
            full_reply = ""
            for chunk in stream_theory_answer(user_input, history):
                full_reply += chunk
                placeholder.markdown(full_reply + "▌")
            placeholder.markdown(full_reply)
        add_chat_message(session_id, "assistant", full_reply)
        st.rerun()

# ── Tab2：知识库 ─────────────────────────────────────────────────────────────
with tab_knowledge:
    st.markdown(f"## {selected_topic}")
    knowledge_path = KNOWLEDGE_DIR / topic_file
    if knowledge_path.exists():
        content = knowledge_path.read_text(encoding="utf-8")
        st.markdown(content)
    else:
        st.warning("知识文件暂不存在")

    st.markdown("---")
    quick_q = st.text_input("💬 对这个知识点有疑问？直接问", placeholder="例如：Newey-West的lag数怎么选择？")
    if quick_q:
        with st.spinner("思考中..."):
            history_local = get_chat_history(session_id, 10)
            add_chat_message(session_id, "user", quick_q)
            reply = ""
            with st.chat_message("assistant", avatar="🤖"):
                ph = st.empty()
                for chunk in stream_theory_answer(quick_q, history_local):
                    reply += chunk
                    ph.markdown(reply + "▌")
                ph.markdown(reply)
            add_chat_message(session_id, "assistant", reply)

# ── Tab3：上传数据主动分析 ────────────────────────────────────────────────────
with tab_upload:
    st.markdown("上传你的数据，AI会主动告诉你可以构造哪些因子。")
    uploaded_file = st.file_uploader("上传数据文件", type=["xlsx", "csv"], key="theory_upload")
    hint = st.text_area("补充说明", placeholder="你的数据是什么，各列含义是什么？", height=80)

    if uploaded_file and st.button("🤖 AI主动分析", type="primary"):
        import pandas as pd
        from llm.data_classifier import classify_dataframe
        try:
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"读取失败：{e}")
            df = None

        if df is not None:
            with st.spinner("AI正在分析你的数据..."):
                classification = classify_dataframe(df, hint)
                proactive_analysis = analyze_uploaded_data_proactively(classification)

            st.markdown("### 🤖 AI主动分析")
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(proactive_analysis)
            add_chat_message(session_id, "assistant", proactive_analysis)
