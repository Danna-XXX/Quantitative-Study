"""
理论学习问答Agent：结合知识库内容回答量化金融理论问题。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import KNOWLEDGE_DIR
from llm.client import chat_completion, stream_completion

SYSTEM_PROMPT = """你是一位量化金融和实证资产定价领域的专业教师，专门帮助金融/经济学研究生学习量化研究方法。

你的教学风格：
- 从直觉出发：先解释经济含义，再讲数学
- 循序渐进：根据学生的理解程度调整深度
- 联系实践：结合A股市场的实际案例
- 鼓励提问：主动询问学生是否理解，引导深入思考

专业覆盖范围：
- 因子定价理论（CAPM, APT, SDF框架）
- 实证资产定价方法（组合排序、FM回归、时序回归）
- 常见因子（规模、价值、动量、质量、低波动等）
- 统计方法（Newey-West、winsorize、标准化、固定效应）
- 数据处理（CSMAR使用、数据清洗、缺失值处理）
- 论文写作（如何汇报结果、表格格式、显著性标注）

回答规范：
- 用中文回答，保留必要的英文术语
- 公式用 LaTeX 格式（$...$）表示
- 对复杂概念分步骤解释
- 适时引用经典文献（Fama-French 1993, Carhart 1997等）"""


def _load_knowledge_context(topic: str) -> str:
    """根据主题加载相关知识文件内容。"""
    topic_map = {
        "因子": "factor_basics.md",
        "capm": "factor_models.md",
        "ff3": "factor_models.md",
        "ff5": "factor_models.md",
        "fama": "factor_models.md",
        "排序": "portfolio_sorting.md",
        "分组": "portfolio_sorting.md",
        "组合": "portfolio_sorting.md",
        "fm回归": "fm_regression.md",
        "截面": "fm_regression.md",
        "fama-macbeth": "fm_regression.md",
        "数据": "data_sources.md",
        "csmar": "data_sources.md",
        "wind": "data_sources.md",
    }
    topic_lower = topic.lower()
    for keyword, filename in topic_map.items():
        if keyword in topic_lower:
            fpath = KNOWLEDGE_DIR / filename
            if fpath.exists():
                return fpath.read_text(encoding="utf-8")
    # 如果没匹配到，加载所有知识文件的摘要（前500字）
    summaries = []
    for f in KNOWLEDGE_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        summaries.append(f"### {f.stem}\n{content[:300]}...")
    return "\n\n".join(summaries)


def answer_theory_question(question: str, history: list[dict]) -> str:
    """非流式：回答理论问题。"""
    context = _load_knowledge_context(question)
    system = SYSTEM_PROMPT
    if context:
        system += f"\n\n【相关参考资料】\n{context[:3000]}"

    messages = [{"role": "system", "content": system}]
    messages += history[-8:]
    messages.append({"role": "user", "content": question})

    return chat_completion(messages, temperature=0.5, max_tokens=1500)


def stream_theory_answer(question: str, history: list[dict]):
    """流式：供Streamlit st.write_stream使用。"""
    context = _load_knowledge_context(question)
    system = SYSTEM_PROMPT
    if context:
        system += f"\n\n【相关参考资料】\n{context[:3000]}"

    messages = [{"role": "system", "content": system}]
    messages += history[-8:]
    messages.append({"role": "user", "content": question})

    yield from stream_completion(messages, temperature=0.5, max_tokens=1500)


def analyze_uploaded_data_proactively(classification_result: dict) -> str:
    """主动分析上传数据，给出因子构造建议。"""
    prompt = f"""用户上传了数据，以下是自动识别结果：

{classification_result}

请主动告诉用户：
1. 你的数据属于什么类型（市场层面/公司截面/文本数据等）
2. 基于这些数据，可以构造哪些因子？（具体说明每种因子的计算方式）
3. 这些因子的理论依据是什么？
4. 还需要补充哪些数据才能开始做回归分析？

语气要像一位热情的导师，让学生感受到数据有很大的研究价值。"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return chat_completion(messages, temperature=0.5, max_tokens=1500)
