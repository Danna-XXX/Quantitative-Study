"""
论文研究顾问Agent：根据数据情况引导学生构建论文框架。
"""
import json
from llm.client import chat_completion, stream_completion

SYSTEM_PROMPT = """你是一位量化金融领域的博士生导师，专注于A股市场的实证资产定价研究。
你的任务是帮助本科生或研究生完成量化因子研究论文，从以下维度引导：

1. **研究问题确定**：帮助学生明确自己的核心研究假设和因子经济逻辑
2. **因子构造建议**：根据原始数据，建议如何构造、变换因子（水平值、差分、标准化等）
3. **论文框架设计**：建议主检验、稳健性检验、机制检验的顺序和内容
4. **数据缺口识别**：指出还需要哪些数据，以及常见的获取渠道（CSMAR、Wind、Tushare等）
5. **计量经济学规范**：提醒winsorize、标准化、Newey-West、行业/年份固定效应等处理

回答风格：
- 用中文回答，专业但不晦涩
- 主动提问，引导学生思考，不要直接给答案
- 具体指出操作步骤，避免泛泛而谈
- 适时举例（如："类似Baker & Stein(2004)的情绪因子构造方法..."）
- 控制回答长度，关键点用bullet points列出"""


def get_research_advice(user_message: str, history: list[dict],
                         data_summary: str = "", paper_stage: str = "framework") -> str:
    """
    非流式：获取一次性建议文字。

    Parameters
    ----------
    user_message : 用户当前消息
    history      : 对话历史 [{"role": "user/assistant", "content": "..."}]
    data_summary : 数据描述（从LLM分类结果生成）
    paper_stage  : 当前阶段 factor_construction/framework/regression_choice/result_interpretation
    """
    system = SYSTEM_PROMPT
    if data_summary:
        system += f"\n\n【用户已上传的数据情况】\n{data_summary}"

    stage_prompts = {
        "factor_construction": "\n\n当前阶段：因子构造。重点引导因子的经济含义和具体计算方法。",
        "framework": "\n\n当前阶段：论文框架商讨。帮助学生确定主检验方法、控制变量、稳健性检验计划。",
        "regression_choice": "\n\n当前阶段：回归方法选择。解释不同方法的适用条件和区别。",
        "result_interpretation": "\n\n当前阶段：结果解读。帮助学生理解回归结果的经济含义和可能的解释。",
    }
    system += stage_prompts.get(paper_stage, "")

    messages = [{"role": "system", "content": system}]
    messages += history[-10:]  # 保留最近10轮
    messages.append({"role": "user", "content": user_message})

    return chat_completion(messages, temperature=0.5, max_tokens=1500)


def stream_research_advice(user_message: str, history: list[dict],
                            data_summary: str = "", paper_stage: str = "framework"):
    """流式版本，供Streamlit st.write_stream使用。"""
    system = SYSTEM_PROMPT
    if data_summary:
        system += f"\n\n【用户已上传的数据情况】\n{data_summary}"

    messages = [{"role": "system", "content": system}]
    messages += history[-10:]
    messages.append({"role": "user", "content": user_message})

    yield from stream_completion(messages, temperature=0.5, max_tokens=1500)


def extract_research_plan(chat_history: list[dict], classification: dict) -> dict:
    """
    分析 Step 2 的对话历史，提取结构化研究计划。

    返回 dict 示例：
    {
      "recommended": [
        {
          "id": "univariate_sort",
          "priority": "primary",
          "badge": "主检验",
          "reason": "用户想初步验证情绪因子预测力",
          "params": {"factor_col": "sentiment_score", "ret_col": "ret", "n_groups": 5}
        },
        ...
      ]
    }
    id 仅限：univariate_sort / fm_regression / independent_double_sort /
             conditional_double_sort / ff3 / ff5
    """
    col_names = list(classification.get("columns", {}).keys()) if classification else []
    col_info = json.dumps(
        {k: v.get("desc", "") for k, v in classification.get("columns", {}).items()},
        ensure_ascii=False
    )

    history_text = "\n".join(
        f"{'用户' if m['role']=='user' else 'AI'}：{m['content']}"
        for m in chat_history[-20:]
    )

    prompt = f"""以下是学生与AI导师关于量化因子论文的商讨记录：

{history_text}

数据列信息（可用列名）：{col_info}
实际列名列表：{col_names}

请根据商讨内容，提取出结构化的研究计划。只输出JSON，格式如下：
{{
  "recommended": [
    {{
      "id": "分析方法ID",
      "priority": "primary/mechanism/robustness",
      "badge": "主检验/机制检验/稳健性检验",
      "reason": "25字以内，说明为什么推荐这个方法（引用对话中的具体内容）",
      "params": {{
        // 从实际列名列表中选择，只填商讨中明确提到的参数
        // 例：factor_col, ret_col, n_groups, control_cols, sort1_col, sort2_col
      }}
    }}
  ]
}}

规则：
1. id 只能是：univariate_sort / fm_regression / independent_double_sort / conditional_double_sort / ff3 / ff5
2. params 中的列名必须来自实际列名列表，不要瞎填
3. 对话中没有明确提到的方法不要加进去，宁缺毋滥
4. 如果对话内容很少，recommended 可以为空列表
5. 只输出JSON，不要有其他文字"""

    messages = [
        {"role": "system", "content": "你是量化金融研究助手，专门从对话中提取结构化研究计划。只输出合法JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = chat_completion(messages, temperature=0.1, max_tokens=1000)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0]
        plan = json.loads(raw)
        # 验证 id 合法
        valid_ids = {"univariate_sort", "fm_regression", "independent_double_sort",
                     "conditional_double_sort", "ff3", "ff5"}
        plan["recommended"] = [r for r in plan.get("recommended", []) if r.get("id") in valid_ids]
        return plan
    except Exception:
        return {"recommended": []}


def suggest_paper_framework(classification_result: dict) -> str:
    """基于数据分类结果，自动生成论文框架建议。"""
    col_types = {
        v["type"]: k for k, v in classification_result.get("columns", {}).items()
    }
    suggestions = classification_result.get("factor_suggestions", [])

    prompt = f"""基于用户上传的数据分析结果：

数据摘要：{classification_result.get('data_summary', '未知')}
因子建议：{json.dumps(suggestions, ensure_ascii=False)}
缺失数据：{json.dumps(classification_result.get('missing_data', []), ensure_ascii=False)}

请为用户设计一个完整的量化因子论文框架，包括：
1. 推荐的主检验方法（按优先级排序）
2. 建议的控制变量
3. 推荐的稳健性检验
4. 可能的机制检验
5. 还需要补充哪些数据

用结构化的格式输出，帮助学生建立清晰的论文写作计划。"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return chat_completion(messages, temperature=0.4, max_tokens=1500)
