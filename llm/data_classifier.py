"""
数据列分类Agent：分析上传的DataFrame，识别每列的含义和数据类型。
"""
import json
import pandas as pd
from llm.client import chat_completion

SYSTEM_PROMPT = """你是一个量化金融数据分析专家。
用户会上传一个数据文件，你需要分析每一列的含义，并将其分类为以下类型之一：
- identifier: 个体标识符（股票代码、公司ID等）
- date: 时间/日期列
- core_factor: 用户研究的核心因子/主要变量（论文中的解释变量）
- return: 股票/资产收益率
- rf: 无风险收益率
- market_factor: 市场层面数据（市场超额收益、SMB、HML、RMW、CMA、动量因子等）
- control_var: 控制变量（市值、账面市值比、动量、换手率等）
- raw_text: 原始文本数据（新闻标题、公告内容等）
- raw_score: 原始打分/评分数据（LLM打分、情绪分等）
- other: 其他难以分类的列

请以JSON格式输出，格式如下：
{
  "columns": {
    "列名1": {"type": "分类", "desc": "中文描述（20字以内）"},
    "列名2": {"type": "分类", "desc": "中文描述"}
  },
  "data_summary": "整体数据描述（100字以内）",
  "factor_suggestions": [
    "建议1：可以用...构造...因子",
    "建议2：..."
  ],
  "missing_data": [
    "缺少无风险收益率，建议从CSMAR的TRD_Nrrate获取",
    "..."
  ],
  "data_quality_notes": "数据质量说明（时间跨度、样本量、缺失情况）"
}

只输出JSON，不要有其他内容。"""


def classify_dataframe(df: pd.DataFrame, user_hint: str = "") -> dict:
    """
    分析DataFrame的列结构，返回LLM的分类结果dict。

    Parameters
    ----------
    df        : 上传的数据
    user_hint : 用户对数据的额外说明
    """
    # 构建列信息摘要
    col_info = {}
    for col in df.columns:
        sample = df[col].dropna().head(5).tolist()
        dtype = str(df[col].dtype)
        col_info[col] = {
            "dtype": dtype,
            "sample": [str(s) for s in sample],
            "n_unique": int(df[col].nunique()),
            "n_null": int(df[col].isna().sum()),
        }

    user_msg = f"""请分析以下数据文件的列结构：

数据形状：{df.shape[0]}行 × {df.shape[1]}列

列详情：
{json.dumps(col_info, ensure_ascii=False, indent=2)}

{"用户补充说明：" + user_hint if user_hint else ""}

请给出完整的列分类结果。"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    try:
        raw = chat_completion(messages, temperature=0.1, max_tokens=2000)
        # 尝试提取JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        return {
            "columns": {col: {"type": "other", "desc": "自动识别失败"} for col in df.columns},
            "data_summary": "自动识别失败，请手动补充列说明。",
            "factor_suggestions": [],
            "missing_data": [],
            "data_quality_notes": f"识别出错: {e}",
        }
