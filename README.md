# QuantResearch Assistant

帮助金融/经济学研究生完成量化因子论文的 AI 助手。从数据上传、因子构造、回归分析到结果解读，全程引导。

## 功能

**理论学习**：与 AI 对话学习量化方法（组合排序、FM 回归、因子模型等），上传数据让 AI 主动分析可构造哪些因子。

**论文实践**：四步引导完成因子研究论文——
1. 上传数据 → AI 自动识别每列含义
2. 与 AI 商讨论文框架（研究问题、控制变量、检验方法）
3. 回归分析（AI 根据商讨结果推荐方法、预填参数）
4. 结果汇总 + 一键导出 Excel

**内置量化分析方法**：
- 单变量分组排序（Newey-West t 检验）
- Fama-MacBeth 截面回归
- 独立双排序 / 条件双排序
- CAPM / FF3 / FF5 时序回归

## 快速开始

**1. 安装依赖**

```bash
pip install -r requirements.txt
```

**2. 配置 API Key**

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key（支持阿里云 / 硅基流动）：

```
LLM_PROVIDER=siliconflow
LLM_API_KEY=sk-你的key
LLM_MODEL=deepseek-ai/DeepSeek-V3
```

阿里云用户：
```
LLM_PROVIDER=aliyun
LLM_API_KEY=sk-你的key
LLM_MODEL=qwen-plus
```

**3. 启动**

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8505`，注册账号即可使用。

## 数据格式

上传面板数据（每行 = 一个公司 × 一个时间点），支持 `.xlsx` 和 `.csv`。

示例列结构：

| Stkcd | YearMonth | sentiment_score | ret | mktcap | rf |
|-------|-----------|----------------|-----|--------|----|
| 000001 | 2020-01 | 0.35 | 0.02 | 1200000 | 0.0003 |

AI 会自动识别哪列是因子、哪列是收益率，并提示缺少哪些数据及获取渠道（CSMAR 等）。

## 项目结构

```
├── app.py                  # 主页入口
├── pages/
│   ├── 1_theory_learning.py
│   └── 2_paper_practice.py
├── quant/                  # 量化分析库
│   ├── univariate_sort.py  # 单变量排序
│   ├── fm_regression.py    # FM 回归
│   ├── double_sort.py      # 独立/条件双排序
│   └── factor_models.py    # CAPM/FF3/FF5
├── llm/                    # LLM 模块
│   ├── client.py           # OpenAI-compatible 客户端
│   ├── data_classifier.py  # 数据列分类
│   ├── research_advisor.py # 论文框架引导
│   ├── result_interpreter.py # 结果解读
│   └── theory_tutor.py     # 理论问答
├── knowledge/              # 理论知识库
├── db/                     # SQLite 数据库
└── components/             # Streamlit UI 组件
```

## 技术栈

- **界面**：Streamlit
- **数据库**：SQLite
- **量化计算**：pandas / numpy / statsmodels / scipy
- **可视化**：Plotly
- **LLM**：OpenAI-compatible API（阿里云 DashScope / 硅基流动）
