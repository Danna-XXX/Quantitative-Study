"""
单变量分组排序（Univariate Portfolio Sort）

核心逻辑：
  期末（形成期）按因子值排序，分N组
  持有下一期的组合收益（超额收益 = ret - rf）
  对 H-L 组合做 Newey-West t 检验
"""
import numpy as np
import pandas as pd
from quant.preprocessing import winsorize, newey_west_tstat, sig_stars, compute_portfolio_return


def run_univariate_sort(
    df: pd.DataFrame,
    factor_col: str,
    ret_col: str,
    date_col: str,
    id_col: str,
    rf_col: str | None = None,
    n_groups: int = 5,
    weight_col: str | None = None,
    nw_lags: int = 4,
) -> dict:
    """
    Parameters
    ----------
    df         : 面板数据，每行为一个（公司, 时间）观测
    factor_col : 排序因子列名（用于t期分组）
    ret_col    : 收益率列名（t+1期持有收益）
    date_col   : 时间列名
    id_col     : 个体ID列名
    rf_col     : 无风险收益率列名，None则超额收益=原始收益
    n_groups   : 分组数（5 or 10）
    weight_col : None=等权，传入市值列则市值加权
    nw_lags    : Newey-West滞后阶数

    Returns
    -------
    dict with keys:
      summary_df     : 各组平均超额收益+t值+显著性+平均公司数
      time_series_df : 时序（每期各组超额收益）
      hl_stats       : {'mean','t','p','stars'} for H-L portfolio
      group_labels   : list of group names
    """
    df = df.copy()
    dates = sorted(df[date_col].unique())

    group_labels = [f"P{i+1}" for i in range(n_groups)]
    hl_label = f"P{n_groups}-P1"

    ts_records = []  # (date, group, excess_ret)

    for i, t in enumerate(dates[:-1]):
        t_next = dates[i + 1]
        formation = df[df[date_col] == t][[id_col, factor_col]].dropna(subset=[factor_col])
        if len(formation) < n_groups * 2:
            continue

        # 分组
        formation = formation.copy()
        formation["_group"] = pd.qcut(
            formation[factor_col], q=n_groups, labels=range(n_groups), duplicates="drop"
        )
        group_map = formation.set_index(id_col)["_group"].to_dict()

        # 持有期超额收益
        holding = df[df[date_col] == t_next].copy()
        holding["_group"] = holding[id_col].map(group_map)
        holding = holding.dropna(subset=["_group", ret_col])
        if rf_col and rf_col in holding.columns:
            holding["_exret"] = holding[ret_col] - holding[rf_col]
        else:
            holding["_exret"] = holding[ret_col]

        for g in range(n_groups):
            subset = holding[holding["_group"] == g]
            port_ret = compute_portfolio_return(subset, "_exret", weight_col)
            ts_records.append({"date": t_next, "group": group_labels[g], "exret": port_ret})

    if not ts_records:
        return {"error": "数据不足，无法完成分组排序"}

    ts_df = pd.DataFrame(ts_records)
    ts_wide = ts_df.pivot(index="date", columns="group", values="exret")[group_labels]
    ts_wide[hl_label] = ts_wide[group_labels[-1]] - ts_wide[group_labels[0]]

    # 统计汇总
    rows = []
    for col in group_labels + [hl_label]:
        mean, t, p = newey_west_tstat(ts_wide[col], nw_lags)
        avg_n = ts_df[ts_df["group"] == col]["exret"].notna().groupby(
            ts_df["date"]
        ).sum().mean() if col in group_labels else float("nan")
        rows.append({
            "组别": col,
            "月均超额收益(%)": round(mean * 100, 4) if not np.isnan(mean) else np.nan,
            "t统计量": round(t, 3) if not np.isnan(t) else np.nan,
            "显著性": sig_stars(p) if not np.isnan(p) else "",
            "p值": round(p, 4) if not np.isnan(p) else np.nan,
        })

    summary_df = pd.DataFrame(rows)

    hl_row = ts_wide[hl_label].dropna()
    hl_mean, hl_t, hl_p = newey_west_tstat(hl_row, nw_lags)
    hl_stats = {
        "mean": round(hl_mean * 100, 4),
        "t": round(hl_t, 3),
        "p": round(hl_p, 4),
        "stars": sig_stars(hl_p),
        "annualized_pct": round(hl_mean * 12 * 100, 2),
    }

    ts_wide_pct = ts_wide * 100
    ts_wide_pct.index = ts_wide_pct.index.astype(str)

    return {
        "summary_df": summary_df,
        "time_series_df": ts_wide_pct.reset_index().rename(columns={"date": "时间"}),
        "hl_stats": hl_stats,
        "group_labels": group_labels,
        "hl_label": hl_label,
        "n_periods": len(ts_wide),
    }
