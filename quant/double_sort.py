"""
双变量排序（Bivariate Portfolio Sort）

独立双排序：两个因子独立分组，取交叉组合（n1 × n2 个格子）
条件双排序：先按因子1分组，组内再按因子2排序（控制因子1后看因子2效果）
"""
import numpy as np
import pandas as pd
from quant.preprocessing import newey_west_tstat, sig_stars, compute_portfolio_return


def _build_portfolios(df: pd.DataFrame, date_col: str, id_col: str,
                       ret_col: str, weight_col: str | None,
                       factor1_col: str, n1: int,
                       factor2_col: str, n2: int,
                       independent: bool) -> pd.DataFrame:
    """
    Returns a DataFrame: index=date, columns=group_labels (e.g. '1-1', '1-2', ..., 'H-L_f2')
    """
    dates = sorted(df[date_col].unique())
    records = []

    for i, t in enumerate(dates[:-1]):
        t_next = dates[i + 1]
        formation = df[df[date_col] == t].dropna(subset=[factor1_col, factor2_col])
        if len(formation) < (n1 * n2 * 2):
            continue

        formation = formation.copy()

        if independent:
            formation["_g1"] = pd.qcut(
                formation[factor1_col], q=n1, labels=range(n1), duplicates="drop"
            )
            formation["_g2"] = pd.qcut(
                formation[factor2_col], q=n2, labels=range(n2), duplicates="drop"
            )
        else:
            # Conditional: sort on f1 first, then sort f2 within each f1 group
            formation["_g1"] = pd.qcut(
                formation[factor1_col], q=n1, labels=range(n1), duplicates="drop"
            )
            formation["_g2"] = formation.groupby("_g1")[factor2_col].transform(
                lambda s: pd.qcut(s, q=n2, labels=range(n2), duplicates="drop")
            )

        grp_map = formation.set_index(id_col)[["_g1", "_g2"]].to_dict(orient="index")

        holding = df[df[date_col] == t_next].copy()
        holding["_g1"] = holding[id_col].map(lambda x: grp_map.get(x, {}).get("_g1"))
        holding["_g2"] = holding[id_col].map(lambda x: grp_map.get(x, {}).get("_g2"))
        holding = holding.dropna(subset=["_g1", "_g2", ret_col])

        row = {"date": t_next}
        for g1 in range(n1):
            for g2 in range(n2):
                subset = holding[(holding["_g1"] == g1) & (holding["_g2"] == g2)]
                row[f"{g1+1}-{g2+1}"] = compute_portfolio_return(subset, ret_col, weight_col)
        records.append(row)

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).set_index("date")


def run_independent_double_sort(
    df: pd.DataFrame,
    factor1_col: str,
    factor2_col: str,
    ret_col: str,
    date_col: str,
    id_col: str,
    n_groups1: int = 5,
    n_groups2: int = 5,
    weight_col: str | None = None,
    nw_lags: int = 4,
    rf_col: str | None = None,
) -> dict:
    """
    独立双排序：两个因子独立按分位数分组，取交叉格子的组合收益。

    Returns
    -------
    dict:
      grid_df       : n1×n2 矩阵，每格为月均超额收益(%)
      hl_by_f1      : 按因子1控制后，因子2的H-L序列统计
      hl_by_f2      : 按因子2控制后，因子1的H-L序列统计
      time_series_df: 时序（所有格子）
    """
    df = df.copy()
    if rf_col and rf_col in df.columns:
        df[ret_col] = df[ret_col] - df[rf_col]

    port_df = _build_portfolios(
        df, date_col, id_col, ret_col, weight_col,
        factor1_col, n_groups1, factor2_col, n_groups2, independent=True
    )
    if port_df.empty:
        return {"error": "数据不足，无法完成独立双排序"}

    # Grid summary
    grid = {}
    for g1 in range(n_groups1):
        row_key = f"F1_P{g1+1}"
        grid[row_key] = {}
        for g2 in range(n_groups2):
            col_key = f"F2_P{g2+1}"
            col = f"{g1+1}-{g2+1}"
            if col in port_df.columns:
                grid[row_key][col_key] = round(port_df[col].mean() * 100, 4)

    grid_df = pd.DataFrame(grid).T

    # H-L for factor2 (within each factor1 group)
    hl_f2_rows = []
    for g1 in range(n_groups1):
        hi_col = f"{g1+1}-{n_groups2}"
        lo_col = f"{g1+1}-1"
        if hi_col in port_df.columns and lo_col in port_df.columns:
            hl_series = port_df[hi_col] - port_df[lo_col]
            mean, t, p = newey_west_tstat(hl_series, nw_lags)
            hl_f2_rows.append({
                "F1分组": f"P{g1+1}",
                "F2 H-L均值(%)": round(mean * 100, 4),
                "t统计量": round(t, 3),
                "显著性": sig_stars(p),
            })

    # H-L for factor1 (within each factor2 group)
    hl_f1_rows = []
    for g2 in range(n_groups2):
        hi_col = f"{n_groups1}-{g2+1}"
        lo_col = f"1-{g2+1}"
        if hi_col in port_df.columns and lo_col in port_df.columns:
            hl_series = port_df[hi_col] - port_df[lo_col]
            mean, t, p = newey_west_tstat(hl_series, nw_lags)
            hl_f1_rows.append({
                "F2分组": f"P{g2+1}",
                "F1 H-L均值(%)": round(mean * 100, 4),
                "t统计量": round(t, 3),
                "显著性": sig_stars(p),
            })

    ts_pct = (port_df * 100).reset_index().rename(columns={"date": "时间"})

    return {
        "grid_df": grid_df,
        "hl_by_f1": pd.DataFrame(hl_f1_rows),
        "hl_by_f2": pd.DataFrame(hl_f2_rows),
        "time_series_df": ts_pct,
        "n_periods": len(port_df),
    }


def run_conditional_double_sort(
    df: pd.DataFrame,
    sort1_col: str,
    sort2_col: str,
    ret_col: str,
    date_col: str,
    id_col: str,
    n_groups1: int = 2,
    n_groups2: int = 5,
    weight_col: str | None = None,
    nw_lags: int = 4,
    rf_col: str | None = None,
) -> dict:
    """
    条件双排序：先按 sort1_col 分 n1 组（通常2组=中位数分割），
    再在各组内按 sort2_col 分 n2 组。

    用途：控制 sort1 特征后，检验 sort2 的因子溢价是否仍然显著。
    例如：控制市值大小后，情绪因子效应是否更强（信息摩擦机制检验）。

    Returns
    -------
    dict:
      conditional_summary: 每个sort1组内的 sort2 H-L 统计
      time_series_df     : 时序
      grid_df            : n1×n2 格子平均收益(%)
    """
    df = df.copy()
    if rf_col and rf_col in df.columns:
        df[ret_col] = df[ret_col] - df[rf_col]

    port_df = _build_portfolios(
        df, date_col, id_col, ret_col, weight_col,
        sort1_col, n_groups1, sort2_col, n_groups2, independent=False
    )
    if port_df.empty:
        return {"error": "数据不足，无法完成条件双排序"}

    cond_rows = []
    group1_labels = ["小" if n_groups1 == 2 else f"G{i+1}" for i in range(n_groups1)]
    for g1 in range(n_groups1):
        hi_col = f"{g1+1}-{n_groups2}"
        lo_col = f"{g1+1}-1"
        if hi_col in port_df.columns and lo_col in port_df.columns:
            hl_series = port_df[hi_col] - port_df[lo_col]
            mean, t, p = newey_west_tstat(hl_series, nw_lags)
            cond_rows.append({
                f"{sort1_col}分组": group1_labels[g1] if g1 == 0 else "大",
                "H-L均值(%)": round(mean * 100, 4),
                "t统计量": round(t, 3),
                "显著性": sig_stars(p),
                "p值": round(p, 4),
            })

    grid = {}
    for g1 in range(n_groups1):
        row_key = group1_labels[g1] if g1 == 0 else "大"
        grid[row_key] = {}
        for g2 in range(n_groups2):
            col_key = f"P{g2+1}"
            col = f"{g1+1}-{g2+1}"
            if col in port_df.columns:
                grid[row_key][col_key] = round(port_df[col].mean() * 100, 4)

    ts_pct = (port_df * 100).reset_index().rename(columns={"date": "时间"})

    return {
        "conditional_summary": pd.DataFrame(cond_rows),
        "grid_df": pd.DataFrame(grid).T,
        "time_series_df": ts_pct,
        "n_periods": len(port_df),
    }
