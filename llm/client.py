import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

_client: OpenAI | None = None


def get_llm_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    return _client


def chat_completion(messages: list[dict], model: str | None = None,
                    temperature: float = 0.3, max_tokens: int = 2048,
                    response_format: dict | None = None) -> str:
    """非流式调用，返回完整回复文字。"""
    client = get_llm_client()
    kwargs = dict(
        model=model or LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if response_format:
        kwargs["response_format"] = response_format
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content


def stream_completion(messages: list[dict], model: str | None = None,
                       temperature: float = 0.5, max_tokens: int = 2048):
    """流式调用，返回 generator（每次 yield 一段文字）。"""
    client = get_llm_client()
    stream = client.chat.completions.create(
        model=model or LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content
