import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.sandwich_covariance import cov_hac


def winsorize(series: pd.Series, pct: float = 0.005) -> pd.Series:
    lo = series.quantile(pct)
    hi = series.quantile(1 - pct)
    return series.clip(lo, hi)


def standardize(series: pd.Series) -> pd.Series:
    mu = series.mean()
    sigma = series.std()
    if sigma == 0:
        return series - mu
    return (series - mu) / sigma


def newey_west_tstat(coef_series: pd.Series, nw_lags: int = 4) -> tuple[float, float, float]:
    """Return (mean, t-stat, p-value) using Newey-West HAC SE."""
    vals = coef_series.dropna().values
    if len(vals) < 3:
        return float("nan"), float("nan"), float("nan")
    n = len(vals)
    mean_val = vals.mean()
    resid = vals - mean_val
    # Newey-West variance
    gamma0 = np.dot(resid, resid) / n
    nw_var = gamma0
    for lag in range(1, nw_lags + 1):
        weight = 1 - lag / (nw_lags + 1)
        gamma_lag = np.dot(resid[lag:], resid[:-lag]) / n
        nw_var += 2 * weight * gamma_lag
    se = np.sqrt(max(nw_var, 1e-16) / n)
    t = mean_val / se
    p = 2 * (1 - stats.t.cdf(abs(t), df=n - 1))
    return float(mean_val), float(t), float(p)


def sig_stars(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def winsorize_cross_section(df: pd.DataFrame, cols: list, pct: float = 0.005) -> pd.DataFrame:
    """Winsorize specified columns within each cross-section (date group)."""
    df = df.copy()
    for col in cols:
        df[col] = df.groupby(df.index)[col].transform(lambda s: winsorize(s, pct))
    return df


def compute_portfolio_return(group_df: pd.DataFrame, ret_col: str,
                              weight_col: str | None = None) -> float:
    """Compute equal-weighted or value-weighted portfolio return."""
    rets = group_df[ret_col].dropna()
    if len(rets) == 0:
        return float("nan")
    if weight_col is None:
        return float(rets.mean())
    weights = group_df.loc[rets.index, weight_col]
    total_w = weights.sum()
    if total_w == 0:
        return float(rets.mean())
    return float((rets * weights).sum() / total_w)
