"""结果表格和图表展示组件"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st


def display_summary_table(df: pd.DataFrame, title: str = ""):
    """展示汇总统计表格（带高亮显著性）"""
    if title:
        st.subheader(title)
    if df.empty:
        st.warning("暂无结果")
        return

    def highlight_sig(row):
        styles = [""] * len(row)
        if "显著性" in row.index:
            sig = row.get("显著性", "")
            if sig == "***":
                styles = ["background-color: #d4edda"] * len(row)
            elif sig == "**":
                styles = ["background-color: #d1ecf1"] * len(row)
            elif sig == "*":
                styles = ["background-color: #fff3cd"] * len(row)
        return styles

    styled = df.style.apply(highlight_sig, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # 显著性图例
    st.caption("🟢 *** p<1%  🔵 ** p<5%  🟡 * p<10%  白色 不显著")


def plot_portfolio_returns(time_series_df: pd.DataFrame, group_labels: list, hl_label: str):
    """绘制各组组合的累计收益曲线"""
    df = time_series_df.copy()
    if "时间" in df.columns:
        df = df.set_index("时间")

    fig = go.Figure()
    colors = px.colors.qualitative.Set2

    for i, col in enumerate(group_labels + [hl_label]):
        if col not in df.columns:
            continue
        cumret = (1 + df[col] / 100).cumprod()
        line_style = dict(width=3, dash="solid") if col == hl_label else dict(width=1.5)
        fig.add_trace(go.Scatter(
            x=df.index, y=cumret,
            name=col, line=dict(color=colors[i % len(colors)], **line_style),
        ))

    fig.update_layout(
        title="各组组合累计收益（指数化）",
        xaxis_title="时间", yaxis_title="累计收益（从1开始）",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_group_bar(summary_df: pd.DataFrame):
    """绘制各分组月均超额收益条形图"""
    if summary_df.empty:
        return
    ret_col = "月均超额收益(%)"
    if ret_col not in summary_df.columns:
        return

    fig = px.bar(
        summary_df,
        x="组别", y=ret_col,
        color=ret_col,
        color_continuous_scale=["#d73027", "#fee08b", "#1a9850"],
        labels={ret_col: "月均超额收益(%)"},
        title="各分组月均超额收益",
    )
    fig.update_layout(height=350, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def plot_coef_timeseries(coef_df: pd.DataFrame, factor_col: str):
    """绘制FM回归系数时序"""
    if coef_df.empty or factor_col not in coef_df.columns:
        return
    time_col = "时间"
    if time_col not in coef_df.columns:
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=coef_df[time_col], y=coef_df[factor_col],
        mode="lines+markers", name=f"{factor_col}系数",
        line=dict(color="#2196F3"),
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title=f"FM回归系数时序：{factor_col}",
        xaxis_title="时间", yaxis_title="系数值",
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_grid_heatmap(grid_df: pd.DataFrame, title: str = "双排序收益矩阵(%)"):
    """绘制双排序格子热力图"""
    if grid_df.empty:
        return
    fig = px.imshow(
        grid_df.astype(float),
        color_continuous_scale=["#d73027", "#fee08b", "#1a9850"],
        text_auto=".3f",
        aspect="auto",
        title=title,
    )
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)


def export_results_to_excel(results_list: list) -> bytes:
    """将所有分析结果导出为多sheet Excel。"""
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for res in results_list:
            analysis_type = res.get("analysis_type", "result")
            result_data = res.get("results_json", {})
            for key, val in result_data.items():
                if isinstance(val, list) and len(val) > 0:
                    try:
                        df_export = pd.DataFrame(val)
                        sheet_name = f"{analysis_type[:8]}_{key[:12]}"[:31]
                        df_export.to_excel(writer, sheet_name=sheet_name, index=False)
                    except Exception:
                        pass
    buf.seek(0)
    return buf.read()
