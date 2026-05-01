"""
回归结果解读Agent：将统计输出转化为经济意义解读。
"""
import json
import pandas as pd
from llm.client import chat_completion

SYSTEM_PROMPT = """你是一位量化金融领域的专家，擅长用通俗易懂的语言解释计量经济学结果。
你的任务是帮助学生理解回归结果的经济含义，并引导他们思考下一步的分析方向。

解读原则：
1. 先解释核心结果（系数大小、显著性）的直接含义
2. 结合金融经济学理论解释为什么会有这个结果
3. 指出结果的局限性和注意事项
4. 提示下一步可以做什么检验来深化/稳健化结论

语言要求：
- 用中文，专业而不晦涩
- 量化表述：提供具体数字（如"因子增加1个标准差，收益率提高X个基点"）
- 经济直觉：联系实际市场行为解释
- 学术规范：使用正确的统计术语"""


def interpret_univariate_sort(result: dict, factor_col: str, context: str = "") -> str:
    """解读单变量分组排序结果"""
    hl = result.get("hl_stats", {})
    summary = result.get("summary_df", pd.DataFrame())

    prompt = f"""请解读以下单变量分组排序（Portfolio Sort）结果：

**核心结果**：
- 因子：{factor_col}
- H-L月均超额收益：{hl.get('mean', 'N/A')}%
- t统计量：{hl.get('t', 'N/A')} {hl.get('stars', '')}
- p值：{hl.get('p', 'N/A')}
- 年化超额收益：约{hl.get('annualized_pct', 'N/A')}%
- 有效期数：{result.get('n_periods', 'N/A')}

**各组收益**：
{summary.to_string(index=False) if not summary.empty else '无'}

{"**背景信息**：" + context if context else ""}

请提供：
1. 结果的直接经济含义（1-2句话，通俗易懂）
2. 统计显著性评价（是否显著、效应大小是否经济上有意义）
3. 单调性分析（P1到P{result.get('n_groups', 5)}是否单调递增）
4. 可能的经济学解释
5. 下一步建议（FM回归控制其他因素？双排序检验机制？）"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return chat_completion(messages, temperature=0.4, max_tokens=1000)


def interpret_fm_regression(result: dict, factor_col: str, control_cols: list,
                              context: str = "") -> str:
    """解读FM回归结果"""
    summary = result.get("summary_df", pd.DataFrame())

    prompt = f"""请解读以下Fama-MacBeth截面回归结果：

**模型**：{factor_col} + 控制变量{control_cols}
**有效期数**：{result.get('n_periods', 'N/A')}

**系数汇总**：
{summary.to_string(index=False) if not summary.empty else '无'}

{"**背景信息**：" + context if context else ""}

请提供：
1. 核心因子系数的直接含义（标准化系数→1倍标准差对应多少基点收益率）
2. 控制变量系数是否符合预期（规模效应、价值效应等）
3. 加入控制变量后因子效果的变化（是否稳健）
4. FM回归vs单变量排序的结果一致性评价
5. 进一步稳健性检验建议"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return chat_completion(messages, temperature=0.4, max_tokens=1000)


def interpret_factor_model(result: dict, model_name: str, context: str = "") -> str:
    """解读CAPM/FF3/FF5 alpha结果"""
    prompt = f"""请解读以下{model_name}时序回归结果：

**Alpha**：{result.get('alpha', 'N/A')}% / 月
**Alpha t统计量**：{result.get('alpha_t', 'N/A')} {result.get('alpha_stars', '')}
**Adj-R²**：{result.get('adj_r2', 'N/A')}
**观测期数**：{result.get('n_obs', 'N/A')}

**因子载荷（Beta）**：
{json.dumps(result.get('betas', {}), ensure_ascii=False, indent=2)}

{"**背景信息**：" + context if context else ""}

请提供：
1. Alpha的经济含义（剔除{model_name}系统风险后，组合还有多少超额收益）
2. 因子载荷的含义（组合向哪个风险方向倾斜）
3. Adj-R²的含义（已知风险因子能解释多少组合收益变动）
4. 如果Alpha显著，说明了什么（因子溢价无法被风险解释）
5. 如果Alpha不显著，可能的原因"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return chat_completion(messages, temperature=0.4, max_tokens=1000)


def interpret_double_sort(result: dict, sort1: str, sort2: str,
                           sort_type: str = "conditional", context: str = "") -> str:
    """解读双排序结果"""
    if sort_type == "conditional":
        cond = result.get("conditional_summary", pd.DataFrame())
        table_str = cond.to_string(index=False) if not cond.empty else "无"
        desc = "条件双排序：先按{}分组，组内按{}排序".format(sort1, sort2)
    else:
        hl_f2 = result.get("hl_by_f2", pd.DataFrame())
        table_str = hl_f2.to_string(index=False) if not hl_f2.empty else "无"
        desc = "独立双排序：{}和{}独立分组".format(sort1, sort2)

    prompt = f"""请解读以下{desc}结果：

{table_str}

{"**背景信息**：" + context if context else ""}

请提供：
1. 双排序设计的经济逻辑（为什么要这样分组）
2. 跨组的H-L差异说明了什么
3. 若存在异质性（不同组H-L差异显著不同），可能的机制解释
4. 这一结果对论文核心假设的支撑作用"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return chat_completion(messages, temperature=0.4, max_tokens=1000)
