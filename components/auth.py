"""登录/注册UI组件"""
import streamlit as st
from db.crud import create_user, verify_user, username_exists


def render_auth():
    """渲染登录/注册界面，返回已登录用户ID（或None）。"""
    st.markdown("""
    <div style='text-align:center; padding: 2rem 0 1rem 0;'>
        <h1>📊 QuantResearch Assistant</h1>
        <p style='color: #666; font-size: 1.1rem;'>量化因子研究智能助手 · 帮助学生做论文</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["登录", "注册"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("用户名", placeholder="输入你的用户名")
            password = st.text_input("密码", type="password", placeholder="输入密码")
            submitted = st.form_submit_button("登录", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("请填写用户名和密码")
            else:
                uid = verify_user(username, password)
                if uid:
                    st.session_state["user_id"] = uid
                    st.session_state["username"] = username
                    st.rerun()
                else:
                    st.error("用户名或密码错误")

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("用户名", placeholder="设置用户名（3-20个字符）")
            new_password = st.text_input("密码", type="password", placeholder="设置密码（至少6位）")
            confirm_password = st.text_input("确认密码", type="password")
            reg_submitted = st.form_submit_button("注册", use_container_width=True)

        if reg_submitted:
            if not new_username or not new_password:
                st.error("请填写所有字段")
            elif len(new_username) < 3:
                st.error("用户名至少3个字符")
            elif len(new_password) < 6:
                st.error("密码至少6位")
            elif new_password != confirm_password:
                st.error("两次密码不一致")
            elif username_exists(new_username):
                st.error("用户名已存在，请换一个")
            else:
                uid = create_user(new_username, new_password)
                st.session_state["user_id"] = uid
                st.session_state["username"] = new_username
                st.success("注册成功！")
                st.rerun()
