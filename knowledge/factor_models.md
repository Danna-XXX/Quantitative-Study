# 因子模型：CAPM / FF3 / FF5

## CAPM（资本资产定价模型）

### 理论
$$r_i - r_f = \alpha_i + \beta_i (r_m - r_f) + \varepsilon_i$$

- $r_f$：无风险收益率
- $r_m - r_f$：市场风险溢价（MKT）
- $\beta_i$：股票 $i$ 的市场风险暴露
- $\alpha_i$（Jensen's Alpha）：扣除市场风险后的超额收益

**核心含义**：CAPM 认为，股票的预期收益**完全**由市场 beta 决定。如果 alpha 显著 > 0，说明该资产有 CAPM 无法解释的超额收益（即**异象/anomaly**）。

### 实践应用
在量化研究中，通常对 **H-L 多空组合** 做 CAPM 回归：
- 如果 alpha 显著，说明因子溢价不能被市场风险解释
- H-L 组合的 beta 通常接近 0（多头和空头的市场风险抵消）

---

## Fama-French 3-Factor Model (FF3)

### 理论（Fama & French, 1993）
$$r_i - r_f = \alpha + b_1 \cdot MKT + b_2 \cdot SMB + b_3 \cdot HML + \varepsilon$$

**三个因子**：
- **MKT**（Market Premium）：市场超额收益 = $r_m - r_f$
- **SMB**（Small Minus Big）：小盘股 - 大盘股收益差（规模因子）
- **HML**（High Minus Low）：高B/M - 低B/M收益差（价值因子）

**经济含义**：
- SMB：小公司面临更高的财务困境风险，需要更高的风险补偿
- HML：高B/M（价值股）面临更高的衰退风险，需要风险补偿

### 在中国的应用
中国国泰安（CSMAR）提供A股FF3因子：
- 数据表：`STK_MKT_THRFACMONTH.xlsx`
- 字段：`RiskPremium1/2`（市场溢价）、`SMB1/2`、`HML1/2`
  - 后缀 1：沪深A股，总市值加权
  - 后缀 2：沪深A股+创业板，总市值加权
- 通常选择 **P9709**（沪深A+创业板，总市值加权）

---

## Fama-French 5-Factor Model (FF5)

### 理论（Fama & French, 2015）
$$r_i - r_f = \alpha + b_1 MKT + b_2 SMB + b_3 HML + b_4 RMW + b_5 CMA + \varepsilon$$

新增两个因子：
- **RMW**（Robust Minus Weak）：高盈利 - 低盈利（盈利因子）
- **CMA**（Conservative Minus Aggressive）：低投资 - 高投资（投资因子）

**理论基础**（股利贴现模型）：
- 盈利能力高的公司，内生价值更高，预期收益更高
- 保守投资（低资本支出）的公司，NPV更高，预期收益更高

**FF5 vs FF3**：
- FF5 解释力更强（更高的 $R^2$）
- 但 HML 在 FF5 中有时变得不显著（因为 HML 部分被 RMW+CMA 解释）

---

## Alpha 的解读

**高 Alpha 的含义**：
$$\alpha > 0, t_{NW} > 2 \Rightarrow \text{因子溢价无法被已知风险解释}$$

有两种解读：
1. **行为金融观点**：投资者存在系统性认知偏差（如过度自信、注意力有限），导致某些股票长期被错误定价
2. **理性定价观点**：还存在我们尚未识别的风险因子，alpha 只是这些未知风险的补偿

**论文中的汇报格式**：

| 模型 | Alpha | t统计量 | 显著性 | Adj-R² |
|------|-------|--------|--------|--------|
| CAPM | 0.423% | 2.87 | *** | 5.2% |
| FF3  | 0.360% | 2.49 | ** | 8.4% |
| FF5  | 0.344% | 2.35 | ** | 9.9% |

→ 三个模型均显著，说明因子溢价对多种风险调整都是稳健的。

---

## 常见问题

**Q：Alpha 小数点后几位？**
A：月度 alpha 通常在 0.1%-0.6% 之间，年化约 1%-7%。报告时保留 2-3 位小数（单位：%）

**Q：Newey-West lag 取多少？**
A：月度时序回归，通常 lag = 4-6；如果时序较长（>100期），可用 $\lfloor 4(T/100)^{2/9} \rfloor$

**Q：H-L 组合的 beta 接近 0 是好事吗？**
A：是的！多空组合的市场 beta 接近 0 说明因子溢价不是简单地来自持有高 beta 股票，而是真正的"因子"溢价
