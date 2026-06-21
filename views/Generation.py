# views/Generation.py
"""Generation Analytics – fuel mix, RE vs fossil, stacked area trends with DOE targets."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from config import (GRIDS, MONTHS, COLORS, RENEWABLE_TYPES,
                    VARIABLE_RE_TYPES, DISPATCHABLE_RE_TYPES,
                    TARGET_RE_2030, TARGET_RE_2040)
from utils.calculations import classify_plant, forecast_re_trajectory, compute_hhi
from components.ui import render_intel_summary

PLANT_PALETTE = {
    "Coal": "#EF4444", "Diesel": "#f4a261", "Gas Turbine": "#ffb703",
    "Combined Cycle / Natural Gas": "#fb8500", "Natural Gas": "#ef8c2d",
    "Thermal": "#EF4444", "Geothermal": "#2DC653", "Hydro": "#00C2FF",
    "Renewable (Wind)": "#90e0ef", "Renewable (Solar)": "#ffd60a",
    "Renewable (Biomass)": "#52b788", "Bio-Gas": "#74c69d",
    "Battery Energy Storage": "#c77dff"
}

def show():
    st.markdown(
        '<h1>Generation Analytics</h1>'
        '<div class="page-description">Fuel mix composition, renewable vs non-renewable analysis, and generation trends</div>',
        unsafe_allow_html=True,
    )

    gen = st.session_state.gen_df
    if gen.empty:
        st.error("Generation data not available.")
        return

    year = st.session_state.global_year
    grid = st.session_state.global_grid

    gen_yr = gen[gen["Year"] == year].copy()
    if grid != "All Grids":
        gen_yr = gen_yr[gen_yr["Grid"] == grid]
        gen_all = gen[gen["Grid"] == grid].copy()
    else:
        gen_yr = gen_yr[gen_yr["Grid"].isin(GRIDS)]
        gen_all = gen[gen["Grid"].isin(GRIDS)].copy()

    total = gen_yr["Generation_MWh"].sum()
    coal = gen_yr[gen_yr["PlantType"] == "Coal"]["Generation_MWh"].sum()
    re = gen_yr[gen_yr["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
    coal_pct = coal / total * 100 if total else 0
    re_pct = re / total * 100 if total else 0

    k1, k2, k3, k4 = st.columns(4)
    def kpi(col, label, val, sub=""):
        col.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{val}</div>'
            f'<div class="kpi-sub">{sub}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    kpi(k1, "Total Generation", f"{total/1e6:.2f} TWh", f"{year}")
    kpi(k2, "Coal Share", f"{coal_pct:.1f}%", "of gross generation")
    kpi(k3, "Renewable Share", f"{re_pct:.1f}%", "of gross generation")
    kpi(k4, "Fossil Fuel Share", f"{100-re_pct:.1f}%", "including gas & diesel")

    # ── Fuel Diversity (HHI) ─────────────────────────────────────────
    fuel_shares_for_hhi = (gen_yr.groupby("PlantType")["Generation_MWh"].sum() / total * 100
                           if total > 0 else pd.Series(dtype=float))
    hhi = compute_hhi(fuel_shares_for_hhi.tolist()) if not fuel_shares_for_hhi.empty else 0
    hhi_label = "Diverse" if hhi < 1500 else ("Moderate" if hhi < 2500 else "Concentrated")
    hhi_color = "#2DC653" if hhi < 1500 else ("#F59E0B" if hhi < 2500 else "#EF4444")

    # ── Generation Intelligence Panel ────────────────────────────────
    all_years = sorted(gen_all["Year"].unique())
    prev_year = all_years[-2] if len(all_years) >= 2 else year

    prev_re = 0
    if prev_year != year:
        prev_gen_yr = gen_all[gen_all["Year"] == prev_year]
        prev_tot = prev_gen_yr["Generation_MWh"].sum()
        prev_re_mwh = prev_gen_yr[prev_gen_yr["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
        prev_re = prev_re_mwh / prev_tot * 100 if prev_tot > 0 else 0

    re_yoy = re_pct - prev_re
    re_gap_2030 = max(0, TARGET_RE_2030 - re_pct)
    re_gap_2040 = max(0, TARGET_RE_2040 - re_pct)

    # Dominant fuel type (excluding broad categories)
    fuel_mix = gen_yr.groupby("PlantType")["Generation_MWh"].sum()
    dominant_fuel = fuel_mix.idxmax() if not fuel_mix.empty else "N/A"
    dominant_pct  = fuel_mix.max() / total * 100 if total > 0 else 0

    # Top RE contributor
    re_mix = gen_yr[gen_yr["PlantType"].isin(RENEWABLE_TYPES)].groupby("PlantType")["Generation_MWh"].sum()
    top_re = re_mix.idxmax() if not re_mix.empty else "N/A"
    top_re_pct = re_mix.max() / total * 100 if (not re_mix.empty and total > 0) else 0

    # Variable vs Dispatchable RE breakdown
    vre_gen = gen_yr[gen_yr["PlantType"].isin(VARIABLE_RE_TYPES)]["Generation_MWh"].sum()
    dre_gen = gen_yr[gen_yr["PlantType"].isin(DISPATCHABLE_RE_TYPES)]["Generation_MWh"].sum()
    vre_pct = vre_gen / total * 100 if total > 0 else 0
    dre_pct = dre_gen / total * 100 if total > 0 else 0

    _re_dir = "increased" if re_yoy >= 0 else "decreased"
    _gen_status = ("CRITICAL" if re_gap_2030 > 15
                   else "ELEVATED" if re_gap_2030 > 10
                   else "WATCH" if re_gap_2030 > 5
                   else "NOMINAL")
    _gen_action = (
        f"Accelerate renewable auctions; target +{re_gap_2030 / max(1, 2030 - year):.1f}pp/yr to reach {TARGET_RE_2030:.0f}% by 2030"
        if re_gap_2030 > 5
        else "Sustain RE growth momentum; advance 2040 trajectory planning"
    )
    render_intel_summary(
        situation=(f"{dominant_fuel} leads at {dominant_pct:.1f}% of total generation. "
                   f"RE share {re_pct:.1f}% — {re_yoy:+.1f}pp vs {prev_year} "
                   f"(VRE {vre_pct:.1f}% | Dispatchable {dre_pct:.1f}%)."),
        impact=(f"RE is {re_gap_2030:.1f}pp below the {TARGET_RE_2030:.0f}% 2030 DOE target. "
                f"Top RE contributor: {top_re} ({top_re_pct:.1f}%). "
                f"Fuel diversity: {hhi_label} (HHI {hhi:.0f})."),
        action=_gen_action,
        impact_status=_gen_status,
        tag="Generation Intel",
    )

    # Row 1: Fuel mix ranking + monthly bar chart
    c1, c2 = st.columns([2, 3])
    with c1:
        st.markdown('<div class="section-header">Fuel Mix Ranking</div>', unsafe_allow_html=True)
        mix = (gen_yr.groupby("PlantType")["Generation_MWh"].sum()
               .reset_index().sort_values("Generation_MWh", ascending=False))
        mix = mix[mix["Generation_MWh"] > 0]
        mix["pct"] = mix["Generation_MWh"] / total * 100 if total > 0 else 0
        max_pct = mix["pct"].max() if not mix.empty else 1
        rows_html = ""
        for _, row in mix.iterrows():
            bar_pct = row["pct"] / max_pct * 100
            color = PLANT_PALETTE.get(row["PlantType"], "#8E9FAF")
            rows_html += f"""<div class="fuel-rank-row">
              <div class="fuel-rank-name">{row['PlantType']}</div>
              <div class="fuel-rank-track">
                <div class="fuel-rank-fill" style="width:{bar_pct:.1f}%;background:{color}"></div>
              </div>
              <div class="fuel-rank-pct">{row['pct']:.1f}%</div>
            </div>"""
        st.markdown(f'<div class="fuel-rank-chart">{rows_html}</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="section-header">Monthly Generation by Plant Type (GWh)</div>', unsafe_allow_html=True)
        st.caption("Monthly generation per plant type. Hydro and solar may show seasonal variations; coal is typically steady.")
        monthly = (gen_yr.groupby(["MonthNum", "Month", "PlantType"])["Generation_MWh"]
                   .sum().reset_index().sort_values("MonthNum"))
        monthly = monthly[monthly["Generation_MWh"] > 0]
        fig2 = px.bar(monthly, x="Month", y="Generation_MWh", color="PlantType",
                      color_discrete_map=PLANT_PALETTE, template="plotly_dark",
                      labels={"Generation_MWh": "GWh", "Month": ""},
                      category_orders={"Month": MONTHS})
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           height=240, legend_title_text="", margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig2, use_container_width=True)

    # RE vs Non-Renewable trend with DOE targets
    st.markdown('<div class="section-header">Renewable vs Non-Renewable Trend (Annual GWh)</div>', unsafe_allow_html=True)
    st.caption("Long‑term trend of renewable vs fossil generation. The renewable area should grow over time to meet DOE targets (35% by 2030, 50% by 2040).")
    gen_all["Category"] = gen_all["PlantType"].apply(classify_plant)
    trend = (gen_all.groupby(["Year", "Category"])["Generation_MWh"]
             .sum().reset_index())
    fig3 = px.area(trend, x="Year", y="Generation_MWh", color="Category",
                   color_discrete_map={"Renewable": "#2DC653", "Non-Renewable": "#EF4444"},
                   template="plotly_dark", labels={"Generation_MWh": "GWh"})
    # Target lines are approximate – show as horizontal references
    if not trend.empty:
        max_recent = trend[trend["Year"] <= 2030]["Generation_MWh"].max() if not trend[trend["Year"] <= 2030].empty else trend["Generation_MWh"].max()
        fig3.add_hline(y=max_recent * (TARGET_RE_2030/100),
                       line_dash="dash", line_color="orange",
                       annotation_text=f"DOE 35% RE by 2030", annotation_position="bottom right")
        fig3.add_hline(y=max_recent * (TARGET_RE_2040/100),
                       line_dash="dash", line_color="yellow",
                       annotation_text=f"DOE 50% RE by 2040", annotation_position="top right")
    fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                       height=240, legend_title_text="", margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig3, use_container_width=True)

    # ── RE 2030/2040 Trajectory Analysis (Phase 3) ───────────────────
    st.markdown('<div class="section-header">RE 2030 Trajectory Analysis</div>', unsafe_allow_html=True)
    re_annual_all = []
    for yr in sorted(gen_all["Year"].unique()):
        yr_df = gen_all[gen_all["Year"] == yr]
        tot_yr = yr_df["Generation_MWh"].sum()
        re_yr  = yr_df[yr_df["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
        re_annual_all.append({"Year": yr, "RE_pct": re_yr / tot_yr * 100 if tot_yr > 0 else 0})
    re_hist_df = pd.DataFrame(re_annual_all)

    proj_2030, slope_yr, ci_lo_30, ci_hi_30 = forecast_re_trajectory(re_hist_df, "Year", "RE_pct", 2030)
    proj_2040, _,        ci_lo_40, ci_hi_40 = forecast_re_trajectory(re_hist_df, "Year", "RE_pct", 2040)

    if proj_2030 is not None:
        on_track_30 = proj_2030 >= TARGET_RE_2030
        on_track_40 = proj_2040 >= TARGET_RE_2040 if proj_2040 is not None else False
        miss_pp_30 = TARGET_RE_2030 - proj_2030
        miss_pp_40 = (TARGET_RE_2040 - proj_2040) if proj_2040 is not None else None
        need_accel = (-miss_pp_30 / max(1, 2030 - year)) if not on_track_30 else 0

        verdict_color_30 = "#2DC653" if on_track_30 else "#EF4444"
        verdict_color_40 = "#2DC653" if on_track_40 else "#EF4444"

        t_col1, t_col2 = st.columns([2, 3])
        with t_col1:
            _proj40_str = f"{proj_2040:.1f}%" if proj_2040 is not None else "N/A"
            _miss40_str = (f"miss by {miss_pp_40:.1f}pp" if (miss_pp_40 is not None and not on_track_40)
                           else ("on track ✓" if on_track_40 else "N/A"))
            _need_pp = (TARGET_RE_2030 - re_pct) / max(1, 2030 - year)
            _traj_status = "NOMINAL" if on_track_30 else ("WATCH" if miss_pp_30 < 5 else "ELEVATED")
            render_intel_summary(
                situation=(f"Projected 2030 RE: {proj_2030:.1f}% — "
                           f"{'on track ✓' if on_track_30 else f'misses target by {miss_pp_30:.1f}pp'}. "
                           f"2040: {_proj40_str} ({_miss40_str})."),
                impact=(f"Current trend: {slope_yr:+.2f}pp/yr. "
                        f"Rate needed for 2030 target: {_need_pp:+.2f}pp/yr."),
                action=("Maintain current RE trajectory." if on_track_30
                        else f"Accelerate +{need_accel:.2f}pp/yr above current trend to close the 2030 gap."),
                impact_status=_traj_status,
                tag="Trajectory",
            )
            if not on_track_30:
                st.markdown(
                    f'<div style="background:rgba(239,68,68,0.08);border-left:3px solid #EF4444;'
                    f'padding:8px 12px;margin-top:4px;border-radius:4px;font-size:12px;color:var(--text-secondary)">'
                    f'At current trend (+{slope_yr:.2f}pp/yr), the 35% target will be missed by {miss_pp_30:.1f}pp. '
                    f'An additional +{need_accel:.2f}pp/yr acceleration is required.'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"""
                <div style="background:rgba(45,198,83,0.08);border-left:3px solid #2dc653;padding:8px 12px;margin-top:8px;border-radius:4px;font-size:12px;color:var(--text-secondary)">
                  At current trend (+{slope_yr:.2f}pp/yr), the 35% target will be met. Maintain deployment pace.
                </div>""", unsafe_allow_html=True)

        with t_col2:
            fig_traj = go.Figure()
            # Historical
            fig_traj.add_trace(go.Scatter(x=re_hist_df["Year"], y=re_hist_df["RE_pct"],
                                          name="Historical RE%", mode="lines+markers",
                                          line=dict(color="#10B981", width=2), marker=dict(size=5)))
            # Trajectory projection
            last_yr = int(re_hist_df["Year"].iloc[-1])
            last_re = float(re_hist_df["RE_pct"].iloc[-1])
            proj_years = list(range(last_yr, 2041))
            proj_vals  = [last_re + slope_yr * (y - last_yr) for y in proj_years]
            margin_30 = max(0, proj_2030 - ci_lo_30) if ci_lo_30 is not None else 0
            ci_scale   = margin_30 / max(1, 2030 - last_yr)
            proj_hi = [v + ci_scale * (y - last_yr) for v, y in zip(proj_vals, proj_years)]
            proj_lo = [v - ci_scale * (y - last_yr) for v, y in zip(proj_vals, proj_years)]
            fig_traj.add_trace(go.Scatter(
                x=proj_years + proj_years[::-1], y=proj_hi + proj_lo[::-1],
                fill="toself", fillcolor="rgba(16,185,129,0.10)",
                line=dict(color="rgba(0,0,0,0)"), name="95% CI", showlegend=False))
            fig_traj.add_trace(go.Scatter(x=proj_years, y=proj_vals, name="Trajectory",
                                          mode="lines", line=dict(color="#10B981", width=2, dash="dot")))
            # Target lines
            fig_traj.add_hline(y=TARGET_RE_2030, line_dash="dash", line_color="rgba(245,158,11,0.8)",
                               annotation_text=f"2030: {TARGET_RE_2030}%", annotation_position="right",
                               annotation_font_size=11)
            fig_traj.add_hline(y=TARGET_RE_2040, line_dash="dash", line_color="rgba(250,204,21,0.6)",
                               annotation_text=f"2040: {TARGET_RE_2040}%", annotation_position="right",
                               annotation_font_size=11)
            fig_traj.update_layout(
                template="plotly_dark", height=240,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=72, t=10, b=0),
                xaxis=dict(tickfont=dict(size=12)),
                yaxis=dict(title="RE Share (%)", tickfont=dict(size=11)),
                legend=dict(orientation="h", y=1.02, x=0, font=dict(size=11)),
                hovermode="x unified",
            )
            st.plotly_chart(fig_traj, use_container_width=True)
    else:
        st.info("Insufficient historical data for trajectory projection (need ≥3 years).")

    # Annual RE Share table
    st.markdown('<div class="section-header">Annual RE Share by Grid (%)</div>', unsafe_allow_html=True)
    st.caption("Percentage of renewable energy per grid, per year. Green cells indicate higher RE share. Compare grids over time.")
    pivot_data = []
    for g in GRIDS:
        g_df = gen[gen["Grid"] == g]
        for yr in sorted(gen["Year"].unique()):
            yr_df = g_df[g_df["Year"] == yr]
            tot = yr_df["Generation_MWh"].sum()
            re_v = yr_df[yr_df["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
            pivot_data.append({"Grid": g, "Year": yr, "RE_pct": re_v/tot*100 if tot>0 else 0})
    re_table = pd.DataFrame(pivot_data).pivot(index="Grid", columns="Year", values="RE_pct")
    re_table.columns = [str(c) for c in re_table.columns]
    st.dataframe(
        re_table.style.format("{:.1f}%")
                       .background_gradient(cmap="Greens", axis=None, vmin=0, vmax=50),
        width="stretch",
    )
    # Grid comparison bar chart
    st.markdown('<div class="section-header">Grid Generation Comparison (GWh)</div>', unsafe_allow_html=True)
    st.caption("Total annual generation per grid. Luzon dominates due to its larger economy and population.")
    comp = (gen[gen["Grid"].isin(GRIDS)]
            .groupby(["Year", "Grid"])["Generation_MWh"]
            .sum().reset_index())
    comp["GWh"] = comp["Generation_MWh"] / 1e3
    fig4 = px.bar(comp, x="Year", y="GWh", color="Grid",
                  color_discrete_map=COLORS, template="plotly_dark",
                  labels={"GWh": "Generation (GWh)"})
    fig4.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                       height=240, legend_title_text="", margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig4, use_container_width=True)

    # ── Export & Downloads ────────────────────────────────────────────
    st.markdown('<div class="section-header export-header">Export & Downloads</div>', unsafe_allow_html=True)
    _gen_csv  = gen_yr.groupby("PlantType")["Generation_MWh"].sum().reset_index().to_csv(index=False)
    _re_csv   = re_table.to_csv()
    _grid_csv = comp.to_csv(index=False)
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        st.download_button("↓ Export Data", _gen_csv,
                           f"generation_fuel_mix_{year}.csv", "text/csv",
                           use_container_width=True)
    with ec2:
        st.download_button("↓ Export Intelligence Brief", _re_csv,
                           "re_share_by_grid.csv", "text/csv",
                           use_container_width=True)
    with ec3:
        st.download_button("↓ Export Full Report", _grid_csv,
                           "grid_generation_trend.csv", "text/csv",
                           use_container_width=True)

    # ── Methodology ───────────────────────────────────────────────────
    with st.expander("Methodology & Data Notes", expanded=False):
        st.markdown(
            '<p style="font-size:13px;color:var(--text-secondary);line-height:1.6">'
            '<b>Data Source:</b> DOE Gross Generation Per Plant Type dataset. '
            '<b>Renewable classification:</b> Geothermal, Hydro, Wind, Solar, Biomass, and Bio-Gas are classified as renewable. '
            '<b>Fuel Diversity (HHI):</b> Herfindahl–Hirschman Index — sum of squared fuel-type share percentages. '
            'HHI &lt; 1,500 = Diverse | 1,500–2,500 = Moderate | &gt;2,500 = Concentrated. '
            '<b>RE trajectory:</b> Linear projection of the annual RE share trend. '
            '<b>DOE targets:</b> 35% RE by 2030, 50% by 2040 per the National Renewable Energy Program.'
            '</p>',
            unsafe_allow_html=True,
        )
