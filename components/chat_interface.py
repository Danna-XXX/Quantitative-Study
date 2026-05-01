"""通用LLM对话组件"""
import streamlit as st


def render_chat_history(messages: list[dict]):
    """渲染对话历史。messages 格式：[{'role': 'user'|'assistant', 'content': '...'}]"""
    for msg in messages:
        with st.chat_message(msg["role"], avatar="🧑‍🎓" if msg["role"] == "user" else "🤖"):
            st.markdown(msg["content"])


def get_user_input(placeholder: str = "输入你的问题...") -> str | None:
    """渲染输入框，返回用户输入（或None）"""
    return st.chat_input(placeholder)


def stream_assistant_response(stream_gen, message_placeholder=None):
    """
    流式展示AI回复。

    Parameters
    ----------
    stream_gen       : generator，每次 yield 一段文字
    message_placeholder : st.empty() 或 None（None则新建chat_message上下文）

    Returns
    -------
    完整回复文字
    """
    full_text = ""
    if message_placeholder is not None:
        for chunk in stream_gen:
            full_text += chunk
            message_placeholder.markdown(full_text + "▌")
        message_placeholder.markdown(full_text)
    else:
        with st.chat_message("assistant", avatar="🤖"):
            placeholder = st.empty()
            for chunk in stream_gen:
                full_text += chunk
                placeholder.markdown(full_text + "▌")
            placeholder.markdown(full_text)
    return full_text
