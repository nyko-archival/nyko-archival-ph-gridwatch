# views/Demand.py
"""Demand Analytics – hourly load curves, monthly peaks, heatmaps, and forecasting."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from config import GRIDS, MONTHS, COLORS
from utils.calculations import forecast_annual_peak
from components.ui import render_intel_summary
from services.intelligence_engine import demand_intel

def show():
    st.markdown(
        '<h1>Demand Analytics</h1>'
        '<div class="page-description">Hourly load curves, monthly peaks, demand growth, and 2-year forecast</div>',
        unsafe_allow_html=True,
    )

    hourly = st.session_state.hourly_df
    if hourly.empty:
        st.error("Hourly demand data not available.")
        return

    # Use global grid filter
    global_grid = st.session_state.global_grid
    if global_grid == "All Grids":
        st.warning("Please select a specific grid for detailed demand analysis.")
        return
    grid = global_grid

    df = hourly[hourly["Grid"] == grid].copy()
    if df.empty:
        st.warning(f"No demand data for {grid}.")
        return

    years_avail = sorted(df["Year"].unique())
    current_year = st.session_state.global_year
    if current_year not in years_avail:
        current_year = max(years_avail)
        st.warning(f"Selected year {st.session_state.global_year} not available. Showing {current_year}.")

    df_yr = df[df["Year"] == current_year].copy()

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    def kpi(col, label, val, sub=""):
        col.markdown(f"""<div class="kpi-card">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{val}</div>
          <div class="kpi-sub">{sub}</div></div>""", unsafe_allow_html=True)

    peak_val = df_yr["DailyPeak_MW"].max()
    avg_val  = df_yr["DailyAvg_MW"].mean()
    growth   = 0.0  # default when no prior-year data
    if current_year > min(years_avail):
        df_prev  = df[df["Year"] == (current_year - 1)]
        prev_avg = df_prev["DailyAvg_MW"].mean()
        growth   = (avg_val - prev_avg) / prev_avg * 100 if prev_avg > 0 else 0.0
        growth_str = f"{growth:+.1f}% vs {current_year - 1}"
    else:
        growth_str = "—"
    low_val    = df_yr["DailyPeak_MW"].min()
    peak_month = df_yr.loc[df_yr["DailyPeak_MW"].idxmax(), "MonthName"] if not df_yr.empty else "—"

    kpi(k1, "Annual Peak Demand", f"{peak_val:,.0f} MW", f"highest daily peak – {peak_month}")
    kpi(k2, "Avg Daily Demand",   f"{avg_val:,.0f} MW",  growth_str)
    kpi(k3, "Lowest Peak",        f"{low_val:,.0f} MW",  "min daily peak")
    kpi(k4, "Days of Data",       f"{len(df_yr):,}",    f"{grid} – {current_year}")

    # ── Demand Intelligence Summary ───────────────────────────────────
    _intel = demand_intel(growth, grid)
    render_intel_summary(
        situation=_intel["situation"],
        impact=f'{_intel["status"]}: {_intel["impact"]}',
        action=_intel["action"],
        impact_status=_intel["status"],
    )

    # Monthly Peak chart
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="section-header">Monthly Peak Demand (MW)</div>', unsafe_allow_html=True)
        st.caption("Highest demand recorded in each month of the selected year. Helps identify seasonal peaks (e.g., summer or holiday periods).")
        monthly_peak = df_yr.groupby(["Month", "MonthName"])["DailyPeak_MW"].max().reset_index().sort_values("Month")
        fig = px.bar(monthly_peak, x="MonthName", y="DailyPeak_MW",
                     color_discrete_sequence=[COLORS[grid]],
                     template="plotly_dark",
                     labels={"DailyPeak_MW": "Peak (MW)", "MonthName": ""})
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          height=240, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<div class="section-header">Annual Peak Demand Trend</div>', unsafe_allow_html=True)
        st.caption("This chart shows the highest single‑day demand for each year. Use it to identify long‑term growth patterns and compare recent peaks with historical values.")
        annual = df.groupby("Year")["DailyPeak_MW"].max().reset_index()
        fig2 = px.line(annual, x="Year", y="DailyPeak_MW",
                       markers=True, template="plotly_dark",
                       color_discrete_sequence=[COLORS[grid]],
                       labels={"DailyPeak_MW": "Peak Demand (MW)"})
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           height=240, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig2, use_container_width=True)

    # Demand forecast (automatically shown)
    st.markdown('<div class="section-header">Peak Demand Forecast (Next 2 Years)</div>', unsafe_allow_html=True)
    st.caption("A simple linear extrapolation of historical annual peaks. The shaded band represents a 95% confidence interval. Use with caution — actual future demand depends on economic growth, energy efficiency, and other factors.")
    future_years, pred, lower, upper = forecast_annual_peak(annual, "Year", "DailyPeak_MW", years_ahead=2)
    if len(future_years) > 0:
        forecast_df = pd.DataFrame({
            "Year": future_years,
            "Forecasted Peak (MW)": pred.round(0),
            "Lower Bound (MW)": lower.round(0),
            "Upper Bound (MW)": upper.round(0)
        })
        st.dataframe(forecast_df, hide_index=True)

        # Plot historical + forecast
        fig_forecast = go.Figure()
        fig_forecast.add_trace(go.Scatter(x=annual["Year"], y=annual["DailyPeak_MW"],
                                          mode="lines+markers", name="Historical",
                                          line=dict(color=COLORS[grid])))
        fig_forecast.add_trace(go.Scatter(x=future_years, y=pred, mode="lines+markers",
                                          name="Forecast", line=dict(color="orange", dash="dash")))
        fig_forecast.add_trace(go.Scatter(x=np.concatenate([future_years, future_years[::-1]]),
                                          y=np.concatenate([upper, lower[::-1]]),
                                          fill="toself", fillcolor="rgba(255,165,0,0.2)",
                                          line=dict(color="rgba(255,165,0,0)"), name="95% CI"))
        fig_forecast.update_layout(template="plotly_dark",
                                   xaxis_title="Year", yaxis_title="Peak (MW)",
                                   height=240,
                                   margin=dict(l=0, r=0, t=10, b=0),
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_forecast, use_container_width=True)
    else:
        st.info("Insufficient historical data for forecasting (need at least 3 years).")

    # Average Hourly Load Curve
    st.markdown('<div class="section-header">Average Hourly Load Curve (MW)</div>', unsafe_allow_html=True)
    st.caption("Typical daily load shape: morning and evening peaks reflect residential and commercial activity. Helps identify when the grid is most stressed.")
    hour_cols = [c for c in df.columns if isinstance(c, (int, float)) and 1 <= c <= 24]
    if not hour_cols:
        hour_cols = [c for c in df.columns if str(c).isdigit() and 1 <= int(str(c)) <= 24]

    if hour_cols:
        hourly_avg = df_yr[hour_cols].apply(pd.to_numeric, errors="coerce").mean()
        hourly_df = pd.DataFrame({"Hour": range(1, len(hourly_avg)+1), "Avg_MW": hourly_avg.values})
        fig3 = px.area(hourly_df, x="Hour", y="Avg_MW",
                       color_discrete_sequence=[COLORS[grid]],
                       template="plotly_dark",
                       labels={"Avg_MW": "Avg Load (MW)", "Hour": "Hour of Day"})
        fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                   height=240, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig3, use_container_width=True)

    # Demand Heatmap
    st.markdown('<div class="section-header">Monthly Average Demand Heatmap (MW)</div>', unsafe_allow_html=True)
    st.caption("Average daily demand per month across years. Darker blue indicates higher demand. Helps spot seasonal trends and long‑term changes.")
    heat = df.groupby(["Year", "Month"])["DailyAvg_MW"].mean().reset_index().pivot(index="Month", columns="Year", values="DailyAvg_MW")
    month_labels = [MONTHS[i-1][:3] for i in heat.index]
    fig4 = px.imshow(heat.values,
                     x=[str(c) for c in heat.columns],
                     y=month_labels,
                     color_continuous_scale="Blues", aspect="auto", template="plotly_dark",
                     labels={"color": "Avg MW"})
    fig4.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                       height=240, margin=dict(l=0,r=0,t=10,b=0),
                       coloraxis_colorbar=dict(
                           title=dict(text="Avg MW", font=dict(color="#F8FAFC", size=11)),
                           tickfont=dict(color="#8E9FAF", size=10),
                           thickness=14,
                           len=0.78,
                           bgcolor="rgba(7,13,25,0.92)",
                           outlinecolor="rgba(30,43,71,0.7)",
                           outlinewidth=1,
                       ))
    st.plotly_chart(fig4, use_container_width=True)

    # ── Export & Downloads ────────────────────────────────────────────
    st.markdown('<div class="section-header export-header">Export & Downloads</div>', unsafe_allow_html=True)
    _demand_csv  = df_yr.to_csv(index=False)
    _annual_csv  = annual.to_csv(index=False)
    _monthly_csv = df_yr.groupby(["Month", "MonthName"])["DailyPeak_MW"].max().reset_index().to_csv(index=False)
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        st.download_button("↓ Export Data", _demand_csv,
                           f"{grid}_demand_{current_year}.csv", "text/csv",
                           use_container_width=True)
    with ec2:
        st.download_button("↓ Export Intelligence Brief", _monthly_csv,
                           f"{grid}_monthly_peaks_{current_year}.csv", "text/csv",
                           use_container_width=True)
    with ec3:
        st.download_button("↓ Export Full Report", _annual_csv,
                           f"{grid}_annual_trend.csv", "text/csv",
                           use_container_width=True)

    # ── Methodology ───────────────────────────────────────────────────
    with st.expander("Methodology & Data Notes", expanded=False):
        st.markdown(
            '<p style="font-size:13px;color:var(--text-secondary);line-height:1.6">'
            '<b>Data Source:</b> NGCP / DOE hourly load data via provided xlsx dataset. '
            '<b>Daily Peak:</b> Maximum hourly reading per calendar day. '
            '<b>Daily Average:</b> Mean of all hourly readings per day. '
            '<b>Forecast:</b> Linear regression on annual peak values — 95% confidence interval derived from residuals. '
            'Forecasts assume historical growth rates continue and do not account for policy interventions or structural demand shifts. '
            '<b>Demand growth rate:</b> Year-on-year percentage change in average daily demand.'
            '</p>',
            unsafe_allow_html=True,
        )
