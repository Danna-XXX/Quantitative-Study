"""回归分析卡片面板"""
import json
import pandas as pd
import streamlit as st

from quant import (
    run_univariate_sort,
    run_fm_regression,
    run_independent_double_sort,
    run_conditional_double_sort,
    run_capm, run_ff3, run_ff5,
)
from components.result_display import (
    display_summary_table, plot_portfolio_returns, plot_group_bar,
    plot_coef_timeseries, plot_grid_heatmap,
)
from llm.result_interpreter import (
    interpret_univariate_sort, interpret_fm_regression,
    interpret_factor_model, interpret_double_sort,
)
from db.crud import save_analysis_result

ANALYSES = [
    {
        "id": "univariate_sort",
        "name": "单变量分组排序",
        "icon": "📊",
        "short_desc": "按因子值分组，检验H-L组合收益",
        "full_desc": """**单变量组合排序（Portfolio Sort）** 是最直观的因子有效性检验。

**经济含义**：如果因子有预测力，高因子组的未来收益应该系统性高于（或低于）低因子组。
H-L = High组收益 - Low组收益，若显著 > 0，说明因子有正向预测力。

**适用场景**：初步验证因子效果，不控制其他特征，是论文第一个主要结果。

**所需数据**：核心因子列 + 收益率列 + 时间列 + 个体ID列（+ 无风险利率）""",
        "requires": ["core_factor", "return", "date", "identifier"],
    },
    {
        "id": "fm_regression",
        "name": "FM截面回归",
        "icon": "📈",
        "short_desc": "控制规模/价值/动量后检验因子净效应",
        "full_desc": """**Fama-MacBeth（1973）截面回归** 是控制已知特征后检验因子效果的标准方法。

**经济含义**：每期做截面OLS，得到因子系数时序，再对系数时序做NW t检验。
系数代表：因子提高1个标准差，预期月超额收益提高多少基点。

**适用场景**：论文的主要检验，证明因子效果独立于规模、价值、动量等。

**所需数据**：核心因子 + 收益率 + 时间 + ID（可选：市值、BM、动量等控制变量）""",
        "requires": ["core_factor", "return", "date", "identifier"],
    },
    {
        "id": "independent_double_sort",
        "name": "独立双排序",
        "icon": "🔲",
        "short_desc": "两因子独立分组，取交叉格子检验",
        "full_desc": """**独立双排序** 将两个因子分别独立排序，产生 N₁×N₂ 个交叉格子。

**经济含义**：
- 检验两个因子是否同时有效（格子内超额收益是否从左下到右上单调递增）
- 分析因子效果是否依赖于另一个因子的水平

**适用场景**：稳健性检验，检验因子效果是否能归结为已知因子。

**所需数据**：两个因子列 + 收益率 + 时间 + ID""",
        "requires": ["core_factor", "return", "date", "identifier"],
    },
    {
        "id": "conditional_double_sort",
        "name": "条件双排序",
        "icon": "🎯",
        "short_desc": "控制变量组内排序，检验机制异质性",
        "full_desc": """**条件双排序（Sequential Sort）** 先按控制变量分组，再在各组内按核心因子排序。

**经济含义**：检验因子效果是否在不同子样本中存在异质性（差异）。
例如：按市值分成大/小盘，若情绪效应在小盘股中更强，支持信息摩擦机制。

**适用场景**：**机制检验**，是论文的重要加分项，增强因子的理论解释力。

**所需数据**：核心因子 + 控制/机制变量 + 收益率 + 时间 + ID""",
        "requires": ["core_factor", "return", "date", "identifier"],
    },
    {
        "id": "ff3",
        "name": "FF3因子模型",
        "icon": "🏛️",
        "short_desc": "三因子调整后的H-L组合Alpha",
        "full_desc": """**Fama-French 3-Factor（FF3）时序回归** 检验 H-L 组合的超额收益能否被三因子解释。

**经济含义**：
- Alpha > 0 且显著：因子溢价无法被市场风险、规模溢价、价值溢价解释
- 这是论文中"排除风险补偿解释"的标准检验

**所需数据**：H-L组合月度收益 + FF3因子（MKT/SMB/HML + 无风险利率）
（FF3因子可从CSMAR `STK_MKT_THRFACMONTH` 获取）""",
        "requires": ["return", "market_factor", "date"],
    },
    {
        "id": "ff5",
        "name": "FF5因子模型",
        "icon": "🏛️",
        "short_desc": "五因子调整后的H-L组合Alpha",
        "full_desc": """**Fama-French 5-Factor（FF5）时序回归** 在FF3基础上加入盈利（RMW）和投资（CMA）因子。

**经济含义**：比FF3更严格的风险调整，如果FF5 Alpha仍然显著，
说明因子溢价无法被更全面的风险因子解释，支持因子的独立有效性。

**所需数据**：H-L组合月度收益 + FF5因子（MKT/SMB/HML/RMW/CMA + 无风险利率）
（FF5因子可从CSMAR `STK_MKT_FIVEFACMONTH` 获取）""",
        "requires": ["return", "market_factor", "date"],
    },
]


BADGE_COLORS = {
    "主检验": "#007bff",
    "机制检验": "#6f42c1",
    "稳健性检验": "#28a745",
}


def _get_factor_columns(classification: dict, target_types: list) -> list:
    """从分类结果中获取指定类型的列名。"""
    return [col for col, info in classification.items() if info.get("type") in target_types]


def _apply_plan_defaults(session_id: int, analysis_id: str, params: dict, df_cols: list):
    """将 research_plan 的建议参数写入 session_state，仅当用户还未手动设置时生效。"""
    key_map = {
        "univariate_sort": {
            "factor_col": f"us_factor_{session_id}",
            "ret_col": f"us_ret_{session_id}",
        },
        "fm_regression": {
            "factor_col": f"fm_factor_{session_id}",
            "control_cols": f"fm_ctrl_{session_id}",
        },
        "conditional_double_sort": {
            "sort1_col": f"ds_f1_{session_id}",
            "sort2_col": f"ds_f2_{session_id}",
        },
        "independent_double_sort": {
            "factor1_col": f"ds_f1_{session_id}",
            "factor2_col": f"ds_f2_{session_id}",
        },
    }
    for param_key, widget_key in key_map.get(analysis_id, {}).items():
        if widget_key not in st.session_state and param_key in params:
            val = params[param_key]
            if isinstance(val, str) and val in df_cols:
                st.session_state[widget_key] = val
            elif isinstance(val, list):
                valid = [v for v in val if v in df_cols]
                if valid:
                    st.session_state[widget_key] = valid


def render_analysis_hub(session_id: int, df: pd.DataFrame, classification: dict,
                         research_plan: dict | None = None):
    """渲染分析面板（6张卡片），如有 research_plan 则重排顺序、加角标、预填参数。"""
    st.subheader("🔬 第三步：选择回归分析方法")

    factor_cols = _get_factor_columns(classification, ["core_factor"])
    return_cols = _get_factor_columns(classification, ["return"])
    date_cols = _get_factor_columns(classification, ["date"])
    id_cols = _get_factor_columns(classification, ["identifier"])
    rf_cols = _get_factor_columns(classification, ["rf"])
    market_cols = _get_factor_columns(classification, ["market_factor"])
    control_cols = _get_factor_columns(classification, ["control_var"])
    df_cols = df.columns.tolist()

    data_ready = bool(factor_cols and return_cols and date_cols and id_cols)

    # ── 根据 research_plan 构建有序卡片列表 ──────────────────────────────────
    plan_map: dict = {}
    recommended_ids: list = []

    if research_plan and research_plan.get("recommended"):
        recommended_ids = [r["id"] for r in research_plan["recommended"]]
        plan_map = {r["id"]: r for r in research_plan["recommended"]}

        # 预填参数默认值（在渲染 widget 之前设置 session_state）
        for rec in research_plan["recommended"]:
            _apply_plan_defaults(session_id, rec["id"], rec.get("params", {}), df_cols)

        # 推荐的先（按 plan 顺序），未提到的补在后面
        rec_analyses = sorted(
            [a for a in ANALYSES if a["id"] in recommended_ids],
            key=lambda a: recommended_ids.index(a["id"])
        )
        other_analyses = [a for a in ANALYSES if a["id"] not in recommended_ids]
        ordered_analyses = rec_analyses + other_analyses

        # 顶部说明
        st.info(
            f"📋 根据你的研究商讨，AI整理了 **{len(recommended_ids)}** 个推荐分析（已按优先级排序，参数已预填）。"
            "其余方法在下方灰色区域，可按需选择。"
        )
    else:
        ordered_analyses = ANALYSES
        st.info("点击卡片查看详细说明，配置参数后运行分析。绿色=数据就绪，黄色=数据可能不足。")

    # ── 渲染推荐卡片 ─────────────────────────────────────────────────────────
    if recommended_ids:
        rec_chunk = [a for a in ordered_analyses if a["id"] in recommended_ids]
        for row_start in range(0, len(rec_chunk), 3):
            cols = st.columns(3)
            for j, analysis in enumerate(rec_chunk[row_start:row_start + 3]):
                plan_info = plan_map[analysis["id"]]
                badge = plan_info.get("badge", "推荐")
                reason = plan_info.get("reason", "")
                color = BADGE_COLORS.get(badge, "#6c757d")
                has_params = bool(plan_info.get("params"))
                with cols[j]:
                    st.markdown(
                        f"""<div style='border:2px solid {color}; border-radius:8px;
                        padding:1rem; background:#f8f9ff; min-height:160px;'>
                        <span style='background:{color}; color:white; padding:2px 8px;
                        border-radius:4px; font-size:0.75rem; font-weight:bold;'>{badge}</span>
                        <h4 style='margin:0.5rem 0 0.3rem 0;'>{analysis["icon"]} {analysis["name"]}</h4>
                        <p style='font-size:0.82rem; color:#444; margin:0;'>{analysis["short_desc"]}</p>
                        <p style='font-size:0.78rem; color:#555; margin:0.4rem 0 0 0;'>💡 {reason}</p>
                        {"<small style='color:#28a745;'>参数已预填 ✓</small>" if has_params else ""}
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    if st.button("查看详情 / 运行", key=f"btn_{analysis['id']}_{session_id}"):
                        st.session_state[f"active_analysis_{session_id}"] = analysis["id"]

        # 分隔线
        other_chunk = [a for a in ordered_analyses if a["id"] not in recommended_ids]
        if other_chunk:
            st.markdown("---")
            st.markdown("<small style='color:#888;'>以下方法未在商讨中提及，可按需选择：</small>",
                        unsafe_allow_html=True)
            for row_start in range(0, len(other_chunk), 3):
                cols = st.columns(3)
                for j, analysis in enumerate(other_chunk[row_start:row_start + 3]):
                    with cols[j]:
                        st.markdown(
                            f"""<div style='border:1px solid #ddd; border-radius:8px;
                            padding:1rem; background:#fafafa; min-height:120px; opacity:0.85;'>
                            <h4 style='color:#666;'>{analysis["icon"]} {analysis["name"]}</h4>
                            <p style='font-size:0.82rem; color:#888;'>{analysis["short_desc"]}</p>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        if st.button("查看详情 / 运行", key=f"btn_{analysis['id']}_{session_id}"):
                            st.session_state[f"active_analysis_{session_id}"] = analysis["id"]
    else:
        # 无 research_plan：原样显示所有卡片
        for row_start in range(0, len(ordered_analyses), 3):
            cols = st.columns(3)
            for j, analysis in enumerate(ordered_analyses[row_start:row_start + 3]):
                with cols[j]:
                    status_color = "#d4edda" if data_ready else "#fff3cd"
                    status_text = "数据就绪 ✓" if data_ready else "数据可能不足 ⚠"
                    st.markdown(
                        f"""<div style='border:1px solid #ddd; border-radius:8px;
                        padding:1rem; background:{status_color}; min-height:130px;'>
                        <h4>{analysis["icon"]} {analysis["name"]}</h4>
                        <p style='font-size:0.85rem; color:#444;'>{analysis["short_desc"]}</p>
                        <small>{status_text}</small></div>""",
                        unsafe_allow_html=True,
                    )
                    if st.button("查看详情 / 运行", key=f"btn_{analysis['id']}_{session_id}"):
                        st.session_state[f"active_analysis_{session_id}"] = analysis["id"]

    # 弹出分析配置
    active = st.session_state.get(f"active_analysis_{session_id}")
    if active:
        analysis = next((a for a in ANALYSES if a["id"] == active), None)
        if analysis:
            st.markdown("---")
            st.subheader(f"{analysis['icon']} {analysis['name']}")
            st.markdown(analysis["full_desc"])
            st.markdown("---")

            result = None

            # ── 单变量排序 ──────────────────────────────────────────────────
            if active == "univariate_sort":
                c1, c2 = st.columns(2)
                with c1:
                    f_col = st.selectbox("核心因子列", factor_cols or df.columns.tolist(),
                                          key=f"us_factor_{session_id}")
                    ret_col = st.selectbox("收益率列", return_cols or df.columns.tolist(),
                                            key=f"us_ret_{session_id}")
                    date_col = st.selectbox("时间列", date_cols or df.columns.tolist(),
                                             key=f"us_date_{session_id}")
                with c2:
                    id_col = st.selectbox("个体ID列", id_cols or df.columns.tolist(),
                                           key=f"us_id_{session_id}")
                    rf_col = st.selectbox("无风险收益率列（可选）",
                                          ["无"] + rf_cols + df.columns.tolist(),
                                          key=f"us_rf_{session_id}")
                    n_groups = st.slider("分组数", 3, 10, 5, key=f"us_ng_{session_id}")

                w_col = st.selectbox("权重（市值加权可选）",
                                      ["等权"] + [c for c in df.columns],
                                      key=f"us_weight_{session_id}")
                nw_lags = st.slider("Newey-West滞后阶数", 2, 12, 4, key=f"us_nw_{session_id}")

                if st.button("🚀 开始计算", type="primary", key=f"run_us_{session_id}"):
                    with st.spinner("计算中..."):
                        result = run_univariate_sort(
                            df=df,
                            factor_col=f_col,
                            ret_col=ret_col,
                            date_col=date_col,
                            id_col=id_col,
                            rf_col=None if rf_col == "无" else rf_col,
                            n_groups=n_groups,
                            weight_col=None if w_col == "等权" else w_col,
                            nw_lags=nw_lags,
                        )

                    if "error" in result:
                        st.error(result["error"])
                    else:
                        _show_univariate_result(result, f_col, session_id)
                        with st.spinner("AI正在解读结果..."):
                            interp = interpret_univariate_sort(result, f_col)
                        st.markdown("### 🤖 AI解读")
                        st.markdown(interp)
                        # 保存结果
                        res_to_save = {
                            "summary": result["summary_df"].to_dict(orient="records"),
                            "hl_stats": result["hl_stats"],
                        }
                        save_analysis_result(session_id, "univariate_sort",
                                              {"factor": f_col, "n_groups": n_groups},
                                              res_to_save, interp)
                        st.success("✅ 结果已保存")

            # ── FM回归 ──────────────────────────────────────────────────────
            elif active == "fm_regression":
                c1, c2 = st.columns(2)
                with c1:
                    f_col = st.selectbox("核心因子列", factor_cols or df.columns.tolist(),
                                          key=f"fm_factor_{session_id}")
                    ret_col = st.selectbox("收益率列（超额）", return_cols or df.columns.tolist(),
                                            key=f"fm_ret_{session_id}")
                    date_col = st.selectbox("时间列", date_cols or df.columns.tolist(),
                                             key=f"fm_date_{session_id}")
                with c2:
                    id_col = st.selectbox("个体ID列", id_cols or df.columns.tolist(),
                                           key=f"fm_id_{session_id}")
                    ctrl = st.multiselect("控制变量（可多选）",
                                          control_cols + df.columns.tolist(),
                                          key=f"fm_ctrl_{session_id}")

                nw_lags = st.slider("Newey-West滞后阶数", 2, 12, 4, key=f"fm_nw_{session_id}")

                if st.button("🚀 开始计算", type="primary", key=f"run_fm_{session_id}"):
                    with st.spinner("计算中..."):
                        result = run_fm_regression(
                            df=df, factor_col=f_col, ret_col=ret_col,
                            date_col=date_col, id_col=id_col,
                            control_cols=ctrl or None, nw_lags=nw_lags,
                        )
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        display_summary_table(result["summary_df"], "FM回归汇总")
                        plot_coef_timeseries(result["coef_timeseries_df"], f_col)
                        with st.spinner("AI正在解读结果..."):
                            interp = interpret_fm_regression(result, f_col, ctrl)
                        st.markdown("### 🤖 AI解读")
                        st.markdown(interp)
                        res_to_save = {"summary": result["summary_df"].to_dict(orient="records")}
                        save_analysis_result(session_id, "fm_regression",
                                              {"factor": f_col, "controls": ctrl},
                                              res_to_save, interp)
                        st.success("✅ 结果已保存")

            # ── 独立/条件双排序 ──────────────────────────────────────────────
            elif active in ("independent_double_sort", "conditional_double_sort"):
                is_cond = active == "conditional_double_sort"
                c1, c2 = st.columns(2)
                with c1:
                    f1 = st.selectbox(
                        "因子1（核心因子）" if not is_cond else "第一排序变量（控制变量，如市值）",
                        factor_cols + control_cols + df.columns.tolist(),
                        key=f"ds_f1_{session_id}"
                    )
                    f2 = st.selectbox("因子2（核心因子）",
                                       factor_cols + df.columns.tolist(),
                                       key=f"ds_f2_{session_id}")
                    ret_col = st.selectbox("收益率列", return_cols or df.columns.tolist(),
                                            key=f"ds_ret_{session_id}")
                with c2:
                    date_col = st.selectbox("时间列", date_cols or df.columns.tolist(),
                                             key=f"ds_date_{session_id}")
                    id_col = st.selectbox("个体ID列", id_cols or df.columns.tolist(),
                                           key=f"ds_id_{session_id}")
                    n1 = st.slider("因子1分组数", 2, 5, 2 if is_cond else 3,
                                    key=f"ds_n1_{session_id}")
                    n2 = st.slider("因子2分组数", 3, 10, 5, key=f"ds_n2_{session_id}")

                if st.button("🚀 开始计算", type="primary", key=f"run_ds_{session_id}"):
                    with st.spinner("计算中..."):
                        if is_cond:
                            result = run_conditional_double_sort(
                                df=df, sort1_col=f1, sort2_col=f2, ret_col=ret_col,
                                date_col=date_col, id_col=id_col,
                                n_groups1=n1, n_groups2=n2,
                            )
                        else:
                            result = run_independent_double_sort(
                                df=df, factor1_col=f1, factor2_col=f2, ret_col=ret_col,
                                date_col=date_col, id_col=id_col,
                                n_groups1=n1, n_groups2=n2,
                            )
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        if is_cond:
                            display_summary_table(result["conditional_summary"], "条件双排序结果")
                        else:
                            display_summary_table(result["hl_by_f2"], "各因子1组内：因子2的H-L")
                        plot_grid_heatmap(result["grid_df"])
                        with st.spinner("AI正在解读结果..."):
                            sort_type = "conditional" if is_cond else "independent"
                            interp = interpret_double_sort(result, f1, f2, sort_type)
                        st.markdown("### 🤖 AI解读")
                        st.markdown(interp)
                        save_analysis_result(session_id, active,
                                              {"f1": f1, "f2": f2},
                                              {"grid": result["grid_df"].to_dict()}, interp)
                        st.success("✅ 结果已保存")

            # ── FF3/FF5 ─────────────────────────────────────────────────────
            elif active in ("ff3", "ff5"):
                st.info("请上传包含H-L组合月度收益和FF因子的数据（CSMAR STK_MKT_THRFACMONTH/FIVEFACMONTH）")
                ff_file = st.file_uploader("上传FF因子数据文件", type=["xlsx", "csv"],
                                            key=f"ff_file_{session_id}")
                if ff_file:
                    ff_df = pd.read_excel(ff_file) if ff_file.name.endswith(".xlsx") else pd.read_csv(ff_file)
                    st.dataframe(ff_df.head(3), use_container_width=True)

                    c1, c2 = st.columns(2)
                    with c1:
                        hl_col = st.selectbox("H-L组合收益列", df.columns.tolist(),
                                               key=f"ff_hl_{session_id}")
                        date_col = st.selectbox("时间对齐列（主数据）", date_cols or df.columns.tolist(),
                                                 key=f"ff_date_{session_id}")
                    with c2:
                        ff_date_col = st.selectbox("时间对齐列（FF因子）", ff_df.columns.tolist(),
                                                    key=f"ff_ffdate_{session_id}")
                        mkt_col = st.selectbox("MKT列（FF数据）", ff_df.columns.tolist(),
                                                key=f"ff_mkt_{session_id}")

                    if active == "ff5":
                        c3, c4 = st.columns(4)
                        smb_col = st.selectbox("SMB列", ff_df.columns.tolist(), key=f"ff_smb_{session_id}")
                        hml_col = st.selectbox("HML列", ff_df.columns.tolist(), key=f"ff_hml_{session_id}")
                        rmw_col = st.selectbox("RMW列", ff_df.columns.tolist(), key=f"ff_rmw_{session_id}")
                        cma_col = st.selectbox("CMA列", ff_df.columns.tolist(), key=f"ff_cma_{session_id}")
                    else:
                        smb_col = st.selectbox("SMB列", ff_df.columns.tolist(), key=f"ff_smb_{session_id}")
                        hml_col = st.selectbox("HML列", ff_df.columns.tolist(), key=f"ff_hml_{session_id}")

                    if st.button("🚀 开始计算", type="primary", key=f"run_ff_{session_id}"):
                        with st.spinner("计算中..."):
                            merged = pd.merge(
                                df[[date_col, hl_col]].dropna(),
                                ff_df.rename(columns={ff_date_col: date_col}),
                                on=date_col, how="inner"
                            )
                            hl = merged[hl_col]
                            if active == "ff3":
                                result = run_ff3(hl, merged[mkt_col], merged[smb_col], merged[hml_col])
                            else:
                                result = run_ff5(hl, merged[mkt_col], merged[smb_col],
                                                  merged[hml_col], merged[rmw_col], merged[cma_col])

                        if "error" in result:
                            st.error(result["error"])
                        else:
                            display_summary_table(result["summary_df"],
                                                   f"{active.upper()} 时序回归结果")
                            with st.spinner("AI正在解读结果..."):
                                interp = interpret_factor_model(result, result.get("model", active))
                            st.markdown("### 🤖 AI解读")
                            st.markdown(interp)
                            res_to_save = {
                                "alpha": result["alpha"],
                                "alpha_t": result["alpha_t"],
                                "adj_r2": result["adj_r2"],
                            }
                            save_analysis_result(session_id, active, {}, res_to_save, interp)
                            st.success("✅ 结果已保存")


def _show_univariate_result(result: dict, factor_col: str, session_id: int):
    """展示单变量排序的完整结果"""
    hl = result["hl_stats"]
    st.metric(
        label=f"H-L 月均超额收益",
        value=f"{hl['mean']}%",
        delta=f"t={hl['t']} {hl['stars']}，年化约{hl['annualized_pct']}%",
    )
    display_summary_table(result["summary_df"], "各分组收益汇总")
    plot_portfolio_returns(result["time_series_df"], result["group_labels"], result["hl_label"])
    plot_group_bar(result["summary_df"])
