"""
Fama-MacBeth 截面回归（Cross-Sectional Regression）

步骤：
  1. 每期对截面数据做 OLS：ret_t = alpha + beta*factor + gamma*controls + eps
  2. 收集每期系数时序 {beta_t}
  3. 对时序用 Newey-West HAC 做 t 检验
"""
import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from quant.preprocessing import winsorize, standardize, newey_west_tstat, sig_stars


def run_fm_regression(
    df: pd.DataFrame,
    factor_col: str,
    ret_col: str,
    date_col: str,
    id_col: str,
    control_cols: list | None = None,
    nw_lags: int = 4,
    winsorize_pct: float = 0.005,
    standardize_x: bool = True,
) -> dict:
    """
    Parameters
    ----------
    df            : 面板数据
    factor_col    : 核心因子列名
    ret_col       : 因变量（超额收益率）列名
    date_col      : 时间列名
    id_col        : 个体ID列名
    control_cols  : 控制变量列名列表，None则仅跑因子
    nw_lags       : Newey-West滞后阶数
    winsorize_pct : 截面winsorize百分位（双尾）
    standardize_x : 是否对每期截面标准化X（使系数可比）

    Returns
    -------
    dict with keys:
      summary_df         : 系数均值+t值+显著性+期数（每个变量一行）
      coef_timeseries_df : 系数时序（每期一行）
      n_periods          : 有效截面期数
    """
    control_cols = control_cols or []
    all_x_cols = [factor_col] + control_cols
    dates = sorted(df[date_col].unique())

    coef_records = []
    for t in dates:
        sub = df[df[date_col] == t].copy()
        needed = [ret_col, factor_col] + control_cols
        sub = sub.dropna(subset=needed)
        if len(sub) < len(all_x_cols) + 5:
            continue

        # 截面 winsorize + 可选标准化
        for col in all_x_cols + [ret_col]:
            sub[col] = winsorize(sub[col], winsorize_pct)
        if standardize_x:
            for col in all_x_cols:
                sub[col] = standardize(sub[col])

        X = add_constant(sub[all_x_cols], has_constant="add")
        y = sub[ret_col]
        try:
            res = OLS(y, X).fit()
        except Exception:
            continue

        row = {"date": t}
        row["intercept"] = res.params.get("const", np.nan)
        for col in all_x_cols:
            row[col] = res.params.get(col, np.nan)
        row["n_obs"] = len(sub)
        coef_records.append(row)

    if len(coef_records) < 3:
        return {"error": "有效截面期数不足（至少需要3期）"}

    coef_df = pd.DataFrame(coef_records).set_index("date")

    # 汇总：每个变量做 Newey-West t 检验
    summary_rows = []
    display_names = {"intercept": "截距", factor_col: f"{factor_col}（核心因子）"}
    for col in control_cols:
        display_names[col] = col

    for col in ["intercept"] + all_x_cols:
        if col not in coef_df.columns:
            continue
        mean, t, p = newey_west_tstat(coef_df[col], nw_lags)
        summary_rows.append({
            "变量": display_names.get(col, col),
            "均值系数": round(mean, 6) if not np.isnan(mean) else np.nan,
            "t统计量": round(t, 3) if not np.isnan(t) else np.nan,
            "显著性": sig_stars(p) if not np.isnan(p) else "",
            "p值": round(p, 4) if not np.isnan(p) else np.nan,
        })

    summary_df = pd.DataFrame(summary_rows)

    coef_ts = coef_df.reset_index().rename(columns={"date": "时间"})
    for col in coef_ts.columns:
        if col != "时间" and col in coef_ts:
            coef_ts[col] = coef_ts[col].round(6)

    return {
        "summary_df": summary_df,
        "coef_timeseries_df": coef_ts,
        "n_periods": len(coef_df),
        "variables": all_x_cols,
    }
