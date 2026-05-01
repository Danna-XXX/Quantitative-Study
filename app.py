"""QuantResearch Assistant — 主页入口"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from db.database import init_db
from db.crud import get_sessions, create_session
from components.auth import render_auth

# ── 初始化 ──────────────────────────────────────────────────────────────────
init_db()

st.set_page_config(
    page_title="QuantResearch Assistant",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── 注入进度保存提示（关闭时弹窗）─────────────────────────────────────────────
st.markdown("""
<script>
window.addEventListener('beforeunload', function(e) {
    e.preventDefault();
    e.returnValue = '是否要保存当前研究进度？';
    return '是否要保存当前研究进度？';
});
</script>
""", unsafe_allow_html=True)

# ── 登录状态检查 ─────────────────────────────────────────────────────────────
if "user_id" not in st.session_state:
    render_auth()
    st.stop()

user_id = st.session_state["user_id"]
username = st.session_state.get("username", "用户")

# ── 主页：模式选择 ───────────────────────────────────────────────────────────
st.markdown(f"""
<div style='text-align:center; padding: 2rem 0;'>
    <h1>📊 QuantResearch Assistant</h1>
    <p style='color: #666; font-size: 1.1rem;'>欢迎回来，<strong>{username}</strong>！选择今天的工作模式</p>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
    <div style='border:2px solid #007bff; border-radius:12px; padding:2rem; text-align:center; min-height:220px;'>
        <div style='font-size:3rem;'>📚</div>
        <h3>理论学习</h3>
        <p style='color:#555;'>与AI老师对话，学习量化金融理论。
        上传数据让AI主动分析，或在知识库中学习因子、回归、数据来源等知识。</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("进入理论学习 →", type="primary", use_container_width=True):
        st.switch_page("pages/1_theory_learning.py")

with col2:
    st.markdown("""
    <div style='border:2px solid #28a745; border-radius:12px; padding:2rem; text-align:center; min-height:220px;'>
        <div style='font-size:3rem;'>📝</div>
        <h3>论文实践操盘</h3>
        <p style='color:#555;'>用你的数据完成完整的量化因子研究。
        从数据上传、因子构造、回归分析到结果解读，AI全程引导。</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("进入论文实践 →", type="primary", use_container_width=True):
        st.switch_page("pages/2_paper_practice.py")

# ── 历史会话快速访问 ─────────────────────────────────────────────────────────
st.markdown("---")
sessions = get_sessions(user_id)

if sessions:
    st.subheader("📂 最近的研究会话")
    recent = sessions[:4]
    cols = st.columns(len(recent))
    for i, s in enumerate(recent):
        with cols[i]:
            mode_icon = "📚" if s["mode"] == "theory" else "📝"
            mode_label = "理论学习" if s["mode"] == "theory" else "论文实践"
            updated = s.get("updated_at", "")[:10]
            st.markdown(f"""
            <div style='border:1px solid #ddd; border-radius:8px; padding:0.8rem; text-align:center;'>
                <div>{mode_icon}</div>
                <small style='color:#666;'>{mode_label}</small>
                <p style='margin:0.3rem 0; font-size:0.9rem;'><strong>{s['session_name'][:16]}</strong></p>
                <small style='color:#aaa;'>{updated}</small>
            </div>
            """, unsafe_allow_html=True)
            page = "pages/1_theory_learning.py" if s["mode"] == "theory" else "pages/2_paper_practice.py"
            if st.button("继续", key=f"continue_{s['id']}", use_container_width=True):
                key = "theory_session_id" if s["mode"] == "theory" else "practice_session_id"
                st.session_state[key] = s["id"]
                st.switch_page(page)

st.markdown("---")
col_logout, col_help = st.columns(2)
with col_logout:
    if st.button("🚪 退出登录", use_container_width=True):
        for key in ["user_id", "username"]:
            st.session_state.pop(key, None)
        st.rerun()
with col_help:
    with st.expander("❓ 使用帮助"):
        st.markdown("""
**快速上手**：
1. 选择「论文实践」→ 上传你的数据文件（.xlsx/.csv）
2. AI会自动识别每列含义，你可以修正
3. 和AI商讨论文框架（研究问题、控制变量、检验方法）
4. 选择回归方法（单变量排序、FM回归等）→ 运行→ 看结果
5. AI解读结果，引导下一步分析

**理论学习**：直接在对话框提问，如"什么是Fama-MacBeth回归？"

**数据格式**：面板数据（每行=一个公司×一个时间点），支持.xlsx和.csv
        """)
