"""
因子模型时序回归（CAPM / FF3 / FF5）

输入：H-L组合月度收益序列 + 因子序列
输出：alpha、beta系数、t统计量、adj-R²
"""
import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from statsmodels.stats.sandwich_covariance import cov_hac
from quant.preprocessing import sig_stars


def _run_ts_regression(y: pd.Series, X: pd.DataFrame, nw_lags: int) -> dict:
    """OLS时序回归 + Newey-West HAC t统计量"""
    aligned = pd.concat([y, X], axis=1).dropna()
    if len(aligned) < 10:
        return {"error": "时序数据不足（至少需要10个观测）"}

    y_vals = aligned.iloc[:, 0]
    X_vals = add_constant(aligned.iloc[:, 1:], has_constant="add")

    model = OLS(y_vals, X_vals).fit()
    # Newey-West HAC 协方差矩阵
    nw_cov = cov_hac(model, nlags=nw_lags)
    nw_se = np.sqrt(np.diag(nw_cov))

    params = model.params
    t_stats = params / nw_se
    from scipy import stats as scipy_stats
    p_vals = 2 * (1 - scipy_stats.t.cdf(np.abs(t_stats), df=model.df_resid))

    result = {
        "n_obs": len(aligned),
        "adj_r2": round(model.rsquared_adj, 4),
        "alpha": round(params["const"] * 100, 4),
        "alpha_t": round(t_stats["const"], 3),
        "alpha_p": round(p_vals[0], 4),
        "alpha_stars": sig_stars(p_vals[0]),
        "betas": {},
    }
    for col in aligned.columns[1:]:
        result["betas"][col] = {
            "coef": round(params[col], 4),
            "t": round(t_stats[col], 3),
            "stars": sig_stars(p_vals[list(params.index).index(col)]),
        }
    return result


def _make_summary_df(result: dict) -> pd.DataFrame:
    if "error" in result:
        return pd.DataFrame([{"指标": "错误", "值": result["error"]}])
    rows = [
        {"参数": "Alpha (月均%)", "系数": result["alpha"],
         "t统计量": result["alpha_t"], "显著性": result["alpha_stars"]},
    ]
    for factor, vals in result["betas"].items():
        rows.append({
            "参数": f"β_{factor}",
            "系数": vals["coef"],
            "t统计量": vals["t"],
            "显著性": vals["stars"],
        })
    rows.append({"参数": "Adj-R²", "系数": result["adj_r2"], "t统计量": "", "显著性": ""})
    rows.append({"参数": "观测期数", "系数": result["n_obs"], "t统计量": "", "显著性": ""})
    return pd.DataFrame(rows)


def run_capm(
    portfolio_ret: pd.Series,
    market_ret: pd.Series,
    rf: pd.Series | float = 0.0,
    nw_lags: int = 4,
) -> dict:
    """
    CAPM时序回归：r_p - rf = alpha + beta*(r_m - rf) + eps

    Parameters
    ----------
    portfolio_ret : H-L组合月度收益序列（%或小数均可，需与market_ret一致）
    market_ret    : 市场超额收益序列（市场收益 - rf）
    rf            : 无风险收益率序列或标量（如已含在market_ret中则传0）
    nw_lags       : Newey-West滞后阶数
    """
    if isinstance(rf, (int, float)):
        exret = portfolio_ret - rf
    else:
        exret = portfolio_ret - rf
    X = pd.DataFrame({"MKT": market_ret})
    result = _run_ts_regression(exret, X, nw_lags)
    result["model"] = "CAPM"
    result["summary_df"] = _make_summary_df(result)
    return result


def run_ff3(
    portfolio_ret: pd.Series,
    mkt: pd.Series,
    smb: pd.Series,
    hml: pd.Series,
    rf: pd.Series | float = 0.0,
    nw_lags: int = 4,
) -> dict:
    """
    FF3时序回归：r_p - rf = alpha + b1*MKT + b2*SMB + b3*HML + eps
    """
    if isinstance(rf, (int, float)):
        exret = portfolio_ret - rf
    else:
        exret = portfolio_ret - rf
    X = pd.DataFrame({"MKT": mkt, "SMB": smb, "HML": hml})
    result = _run_ts_regression(exret, X, nw_lags)
    result["model"] = "Fama-French 3-Factor"
    result["summary_df"] = _make_summary_df(result)
    return result


def run_ff5(
    portfolio_ret: pd.Series,
    mkt: pd.Series,
    smb: pd.Series,
    hml: pd.Series,
    rmw: pd.Series,
    cma: pd.Series,
    rf: pd.Series | float = 0.0,
    nw_lags: int = 4,
) -> dict:
    """
    FF5时序回归：r_p - rf = alpha + b1*MKT + b2*SMB + b3*HML + b4*RMW + b5*CMA + eps
    """
    if isinstance(rf, (int, float)):
        exret = portfolio_ret - rf
    else:
        exret = portfolio_ret - rf
    X = pd.DataFrame({"MKT": mkt, "SMB": smb, "HML": hml, "RMW": rmw, "CMA": cma})
    result = _run_ts_regression(exret, X, nw_lags)
    result["model"] = "Fama-French 5-Factor"
    result["summary_df"] = _make_summary_df(result)
    return result
