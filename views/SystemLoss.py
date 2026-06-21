# views/SystemLoss.py
"""System Loss – monthly trends, grid comparison, efficiency monitoring."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from config import GRIDS, MONTHS, COLORS, TARGET_SYSTEM_LOSS, WESM_MARGINAL_COST_PER_KWH
from utils.calculations import detect_loss_anomalies
from services.classification_engine import (
    classify_system_loss, SYSTEM_LOSS_THRESHOLDS, STATUS_COLORS,
)
from services.intelligence_engine import system_loss_intel, single_grid_loss_intel
from components.ui import render_intel_summary


def show():
    st.markdown(
        '<h1>System Loss Dashboard</h1>'
        '<div class="page-description">Transmission system loss trends, grid comparison, and efficiency monitoring</div>',
        unsafe_allow_html=True,
    )

    sl = st.session_state.sl_df
    if sl.empty:
        st.error("System loss data not available.")
        return

    year = st.session_state.global_year
    grid = st.session_state.global_grid
    _nat = (grid == "All Grids")
    gen_mwh = st.session_state.gen_df

    grids_to_show = GRIDS + ["Philippines"] if _nat else [grid]

    def get_annual(grid_name, yr=None):
        _yr = yr if yr is not None else year
        row = sl[(sl["Grid"] == grid_name) & (sl["Year"] == _yr) & (sl["Month"] == "Total")]
        return row["SystemLoss_pct"].mean() if not row.empty else None

    ph_sl = get_annual("Philippines")
    lz_sl = get_annual("Luzon")
    vi_sl = get_annual("Visayas")
    mn_sl = get_annual("Mindanao")

    # ── Pre-compute single-grid variables ─────────────────────────────────
    _g_sl = _g_sl_prev = _trend_pp = _intel = None
    _g_class = _g_color = _doe_gap_g = _eco_str = None
    _gen_g_tot = 0

    if not _nat:
        _g_sl      = get_annual(grid)
        _g_sl_prev = get_annual(grid, year - 1)
        _trend_pp  = (_g_sl - _g_sl_prev) if (_g_sl is not None and _g_sl_prev is not None) else 0.0
        _doe_gap_g = round(_g_sl - TARGET_SYSTEM_LOSS, 3) if _g_sl is not None else None
        _g_class   = classify_system_loss(_g_sl) if _g_sl is not None else "N/A"
        _g_color   = STATUS_COLORS.get(_g_class, "#8E9FAF")
        _gen_g_tot = (gen_mwh[(gen_mwh["Year"] == year) & (gen_mwh["Grid"] == grid)]["Generation_MWh"].sum()
                      if not gen_mwh.empty else 0)
        if _gen_g_tot == 0 and not gen_mwh.empty:
            _gen_g_tot = gen_mwh[gen_mwh["Year"] == year]["Generation_MWh"].sum() / 3
        _eco_pesos  = _gen_g_tot * ((_g_sl or 0) / 100) * WESM_MARGINAL_COST_PER_KWH
        _eco_str    = (f"₱{_eco_pesos/1e9:.1f}B" if _eco_pesos >= 1e9
                       else f"₱{_eco_pesos/1e6:.0f}M" if _eco_pesos >= 1e6
                       else f"₱{_eco_pesos/1e3:.0f}K" if _eco_pesos >= 1e3
                       else "< ₱1K")
        _intel = single_grid_loss_intel(grid, _g_sl or 0, _trend_pp)

    # ── KPI Cards ─────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    def kpi(col, label, val, sub="", color="#FFFFFF"):
        col.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value" style="color:{color}">{val}</div>'
            f'<div class="kpi-sub">{sub}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if _nat:
        kpi(k1, "Philippines Avg", f"{ph_sl:.2f}%" if ph_sl else "N/A", f"{year} annual total")
        kpi(k2, "Luzon",          f"{lz_sl:.2f}%" if lz_sl else "N/A", "transmission loss")
        kpi(k3, "Visayas",        f"{vi_sl:.2f}%" if vi_sl else "N/A", "transmission loss")
        kpi(k4, "Mindanao",       f"{mn_sl:.2f}%" if mn_sl else "N/A", "transmission loss")
    else:
        if _g_sl is not None and _g_sl_prev is not None:
            _t_arrow  = "↑" if _trend_pp > 0.005 else ("↓" if _trend_pp < -0.005 else "→")
            _trend_sub = f"{_t_arrow} {_trend_pp:+.3f}pp vs {year - 1}"
        else:
            _trend_sub = f"— no {year - 1} data"
        _pct_above = (_doe_gap_g / TARGET_SYSTEM_LOSS * 100) if (_doe_gap_g and _doe_gap_g > 0) else 0

        kpi(k1, f"{grid} Loss",
            f"{_g_sl:.2f}%" if _g_sl is not None else "N/A",
            _trend_sub, _g_color or "#8E9FAF")
        kpi(k2, "DOE Target",
            f"{TARGET_SYSTEM_LOSS:.2f}%",
            "Philippine mandate", "#10B981")
        kpi(k3, "DOE Gap",
            f"{_doe_gap_g:+.3f}pp" if _doe_gap_g is not None else "N/A",
            f"{_pct_above:.0f}% above target" if _pct_above > 0 else "within mandate",
            "#EF4444" if (_doe_gap_g or 0) > 0 else "#10B981")
        kpi(k4, "Classification",
            _g_class or "N/A",
            SYSTEM_LOSS_THRESHOLDS.get(_g_class or "", "loss severity level"),
            _g_color or "#8E9FAF")

    # ── Loss Intelligence Panel ────────────────────────────────────────────
    grid_vals = {k: v for k, v in
                 {"Luzon": lz_sl, "Visayas": vi_sl, "Mindanao": mn_sl}.items()
                 if v is not None}

    if _nat and grid_vals:
        # ── National: compact intelligence banner ─────────────────────────
        nat_loss = ph_sl if ph_sl is not None else 0
        _sl_intel = system_loss_intel(nat_loss, grid_vals)
        best_grid = min(grid_vals, key=grid_vals.get)
        worst_grid = max(grid_vals, key=grid_vals.get)
        gen_yr_tot = (gen_mwh[gen_mwh["Year"] == year]["Generation_MWh"].sum()
                      if not gen_mwh.empty else 1e8)
        eco_pesos = gen_yr_tot * (nat_loss / 100) * WESM_MARGINAL_COST_PER_KWH
        nat_eco = (f"₱{eco_pesos/1e9:.1f}B" if eco_pesos >= 1e9
                   else f"₱{eco_pesos/1e6:.0f}M" if eco_pesos >= 1e6
                   else f"₱{eco_pesos/1e3:.0f}K")
        render_intel_summary(
            situation=(f"{_sl_intel['situation']} "
                       f"Best: {best_grid} ({grid_vals[best_grid]:.2f}%); "
                       f"worst: {worst_grid} ({grid_vals[worst_grid]:.2f}%)."),
            impact=f"{_sl_intel['status']}: {_sl_intel['impact']} Est. economic impact: {nat_eco}/yr.",
            action=_sl_intel["action"],
            impact_status=_sl_intel["status"],
            tag="Loss Intel",
        )

    elif not _nat and _intel is not None:
        # ── Single-grid: compact intelligence banner ───────────────────────
        _t_word = ("Improving" if (_trend_pp or 0) < -0.02
                   else "Worsening" if (_trend_pp or 0) > 0.02
                   else "Stable")
        _t_str = (f"{'↓' if (_trend_pp or 0) < -0.02 else '↑' if (_trend_pp or 0) > 0.02 else '→'}"
                  f" {(_trend_pp or 0):+.3f}pp vs {year - 1}"
                  if _g_sl_prev is not None else "—")
        render_intel_summary(
            situation=f"{grid} Grid: {_intel['driver']}. Trend: {_t_str} ({_t_word}).",
            impact=f"{_intel['status']}: {_intel['risk']} Est. economic impact: {_eco_str}/yr.",
            action=_intel["action"],
            impact_status=_intel["status"],
            tag=f"{grid} Loss Intel",
        )

        # Benchmark comparison
        _best_g   = min(grid_vals, key=grid_vals.get) if grid_vals else None
        _best_v   = grid_vals.get(_best_g, None) if _best_g else None
        _best_str = f"{_best_v:.2f}% ({_best_g})" if (_best_g and _best_v is not None) else "—"
        _ph_str   = f"{ph_sl:.2f}%" if ph_sl is not None else "—"

        bench_html = (
            f'<div class="loss-benchmark-panel">'
            f'<div class="lbp-header">Loss Benchmark — {year}</div>'
            f'<div class="lbp-grid">'
            f'<div class="lbp-item"><div class="lbp-label">{grid} (Selected)</div>'
            f'<div class="lbp-value" style="color:{_g_color}">{(_g_sl or 0):.2f}%</div></div>'
            f'<div class="lbp-item"><div class="lbp-label">DOE Target</div>'
            f'<div class="lbp-value" style="color:#10B981">{TARGET_SYSTEM_LOSS:.2f}%</div></div>'
            f'<div class="lbp-item"><div class="lbp-label">National Avg</div>'
            f'<div class="lbp-value">{_ph_str}</div></div>'
            f'<div class="lbp-item"><div class="lbp-label">Best Grid</div>'
            f'<div class="lbp-value" style="color:#10B981">{_best_str}</div></div>'
            f'</div></div>'
        )
        st.markdown(bench_html, unsafe_allow_html=True)

        # Executive action box
        if _intel["status"] == "CRITICAL":
            _actions = [
                "Commission NGCP emergency transmission audit",
                "Fast-track priority line rehabilitation",
                "Mandate loss reduction KPIs in NGCP franchise agreement",
            ]
        elif _intel["status"] == "ELEVATED":
            _actions = [
                "Initiate targeted line rehabilitation programme",
                "Mandate annual transmission loss reduction targets",
                "Deploy advanced real-time loss monitoring",
            ]
        else:
            _actions = [
                "Reconductor aging transmission lines",
                "Upgrade aging substations in high-loss segments",
                "Deploy real-time grid monitoring systems",
            ]
        _actions_html = "".join(f'<div class="eab-action">• {a}</div>' for a in _actions)
        _impact_pp    = round(_intel.get("impact_est", 0.2), 2)

        exec_html = (
            f'<div class="exec-action-box">'
            f'<div class="eab-header">Executive Recommendation</div>'
            f'<div class="eab-grid">'
            f'<div class="eab-item"><div class="eab-label">Priority</div>'
            f'<div class="eab-value" style="color:{_g_color}">{_intel["priority"]}</div></div>'
            f'<div class="eab-item"><div class="eab-label">Est. Impact</div>'
            f'<div class="eab-value">−{_impact_pp:.2f}pp loss reduction</div></div>'
            f'<div class="eab-item"><div class="eab-label">Timeline</div>'
            f'<div class="eab-value">12–24 months</div></div>'
            f'</div>'
            f'<div class="eab-actions">{_actions_html}</div>'
            f'</div>'
        )
        st.markdown(exec_html, unsafe_allow_html=True)

    # ── Charts ─────────────────────────────────────────────────────────────
    _label = "All Grids" if _nat else grid
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(f'<div class="section-header">{_label} Annual System Loss Trend</div>',
                    unsafe_allow_html=True)
        st.caption("Yearly loss %. Rising = worsening efficiency. DOE target shown as dashed green line.")
        ann = sl[(sl["Month"] == "Total") & (sl["Grid"].isin(grids_to_show))].copy()
        fig = px.line(ann, x="Year", y="SystemLoss_pct", color="Grid",
                      color_discrete_map=COLORS, markers=True, template="plotly_dark",
                      labels={"SystemLoss_pct": "Loss (%)"})
        fig.add_hline(y=TARGET_SYSTEM_LOSS, line_dash="dash", line_color="green",
                      annotation_text=f"DOE {TARGET_SYSTEM_LOSS}%", annotation_position="bottom right")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          height=240, legend_title_text="", margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown(f'<div class="section-header">{_label} Monthly Loss Profile — {year}</div>',
                    unsafe_allow_html=True)
        st.caption("Monthly variation — losses often higher in summer months due to elevated line resistance.")
        mon = sl[(sl["Year"] == year) & (sl["Month"].isin(MONTHS))
                 & (sl["Grid"].isin(grids_to_show))].copy()
        if not mon.empty:
            mon["MonthNum"] = mon["Month"].apply(lambda m: MONTHS.index(m) + 1 if m in MONTHS else 99)
            mon = mon.sort_values("MonthNum")
            fig2 = px.line(mon, x="Month", y="SystemLoss_pct", color="Grid",
                           color_discrete_map=COLORS, markers=True, template="plotly_dark",
                           category_orders={"Month": MONTHS},
                           labels={"SystemLoss_pct": "Loss (%)", "Month": ""})
            fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               height=240, legend_title_text="", margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig2, use_container_width=True)

    # ── Heatmaps ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">System Loss Heatmap — Monthly × Yearly</div>',
                unsafe_allow_html=True)
    st.caption("Color intensity shows loss magnitude: red = high loss (bad), green = low loss (good).")
    tabs = st.tabs(grids_to_show)
    for i, g in enumerate(grids_to_show):
        with tabs[i]:
            gdf = sl[(sl["Grid"] == g) & (sl["Month"].isin(MONTHS))].copy()
            if gdf.empty:
                st.info(f"No monthly data for {g}")
                continue
            gdf["MonthNum"] = gdf["Month"].apply(lambda m: MONTHS.index(m) + 1)
            gdf = gdf.sort_values("MonthNum")
            pivot = gdf.pivot(index="Month", columns="Year", values="SystemLoss_pct")
            pivot = pivot.reindex([m for m in MONTHS if m in pivot.index])
            fig3 = px.imshow(pivot.values,
                             x=[str(c) for c in pivot.columns],
                             y=[m[:3] for m in pivot.index],
                             color_continuous_scale="RdYlGn_r", aspect="auto",
                             template="plotly_dark", labels={"color": "Loss %"})
            fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               height=240, margin=dict(l=0, r=0, t=10, b=0),
                               coloraxis_colorbar=dict(
                                   title=dict(text="Loss %", font=dict(color="#F8FAFC", size=11)),
                                   tickfont=dict(color="#8E9FAF", size=10),
                                   thickness=14, len=0.78,
                                   bgcolor="rgba(7,13,25,0.92)",
                                   outlinecolor="rgba(30,43,71,0.7)", outlinewidth=1,
                               ))
            st.plotly_chart(fig3, use_container_width=True)

    # ── Loss Anomaly Intelligence ──────────────────────────────────────────
    st.markdown('<div class="section-header">Loss Anomaly Intelligence</div>', unsafe_allow_html=True)
    st.caption("Statistical detection of months deviating ≥2σ from historical seasonal mean.")

    monthly_for_anomaly = sl[(sl["Month"].isin(MONTHS)) & (sl["Grid"].isin(GRIDS))].copy()
    if not monthly_for_anomaly.empty:
        anomaly_df = detect_loss_anomalies(
            monthly_for_anomaly, "Grid", "Year", "Month", "SystemLoss_pct", sigma=2.0)
        if anomaly_df.empty:
            st.info("No statistical anomalies detected across available monthly data (±2σ threshold).")
        else:
            current_anomalies = anomaly_df[anomaly_df["Year"] == year]
            all_anomalies     = anomaly_df.copy()
            if not current_anomalies.empty:
                st.markdown(f"**{year} anomalies detected ({len(current_anomalies)}):**")
                rows_html = ""
                for _, row in current_anomalies.iterrows():
                    dc = "#EF4444" if row["Direction"] == "High" else "#2DC653"
                    dl = "▲ High" if row["Direction"] == "High" else "▼ Low"
                    rows_html += (
                        f'<tr>'
                        f'<td style="color:var(--text-primary)">{row["Grid"]}</td>'
                        f'<td>{row["Month"]}</td>'
                        f'<td style="color:{dc};font-weight:600">{row["Loss_pct"]:.3f}%</td>'
                        f'<td>{row["Historical_Mean"]:.3f}%</td>'
                        f'<td style="color:{dc}">{row["Z_Score"]:+.1f}σ</td>'
                        f'<td style="color:{dc};font-size:11px">{dl}</td>'
                        f'</tr>'
                    )
                st.markdown(
                    '<table class="roadmap-table"><thead><tr>'
                    '<th>Grid</th><th>Month</th><th>Actual Loss</th>'
                    '<th>Historical Avg</th><th>Deviation</th><th>Classification</th>'
                    f'</tr></thead><tbody>{rows_html}</tbody></table>',
                    unsafe_allow_html=True,
                )
            else:
                st.success(f"No anomalies for {year}. All monthly losses within ±2σ of historical norms.")

            with st.expander(f"Full anomaly history ({len(all_anomalies)} events across all years)"):
                st.dataframe(
                    all_anomalies[["Year", "Grid", "Month", "Loss_pct", "Historical_Mean", "Z_Score", "Direction"]]
                    .rename(columns={"Loss_pct": "Loss (%)", "Historical_Mean": "Hist. Mean (%)", "Z_Score": "Z-Score"})
                    .reset_index(drop=True),
                    use_container_width=True, hide_index=True,
                )
                st.download_button("↓ Download Anomaly History CSV",
                                   all_anomalies.to_csv(index=False),
                                   "loss_anomalies.csv", "text/csv")

    # ── Annual Summary Table ───────────────────────────────────────────────
    st.markdown('<div class="section-header">Annual Summary Table</div>', unsafe_allow_html=True)
    st.caption("Yearly system loss for all grids. Red = higher losses; green = better efficiency.")
    pivot_tbl = sl[sl["Month"] == "Total"].pivot(index="Grid", columns="Year", values="SystemLoss_pct")
    pivot_tbl.columns = [str(c) for c in pivot_tbl.columns]
    st.dataframe(pivot_tbl.style.format("{:.2f}%").background_gradient(cmap="RdYlGn_r", axis=None),
                 width="stretch")

    # ── Page Summary (single-grid only) ───────────────────────────────────
    if not _nat and _g_sl is not None and _intel is not None:
        _trend_word = ("Improving" if _trend_pp < -0.02
                       else "Worsening" if _trend_pp > 0.02 else "Stable")
        _issue_map  = {
            "CRITICAL": "Transmission efficiency critically below DOE target — urgent rehabilitation required",
            "ELEVATED": "Transmission losses above DOE 2% mandate — intervention required",
            "WATCH":    "Losses marginally above DOE target — monitoring and maintenance needed",
            "NOMINAL":  "Transmission efficiency within DOE mandate — maintain programme",
        }
        _eco_pesos_final = _gen_g_tot * (_g_sl / 100) * WESM_MARGINAL_COST_PER_KWH
        _eco_final  = (f"₱{_eco_pesos_final/1e6:.0f}M" if _eco_pesos_final >= 1e6
                       else f"₱{_eco_pesos_final/1e3:.0f}K")

        summary_html = (
            f'<div class="sl-summary-panel">'
            f'<div class="slsp-header">System Loss Summary — {grid} Grid {year}</div>'
            f'<div class="slsp-grid">'
            f'<div class="slsp-item"><div class="slsp-label">Current Status</div>'
            f'<div class="slsp-value" style="color:{STATUS_COLORS.get(_g_class or "", "#F59E0B")}">'
            f'{_g_class}</div></div>'
            f'<div class="slsp-item"><div class="slsp-label">Trend</div>'
            f'<div class="slsp-value">{_trend_word}</div></div>'
            f'<div class="slsp-item"><div class="slsp-label">Primary Issue</div>'
            f'<div class="slsp-value">{_issue_map.get(_g_class or "", "—")}</div></div>'
            f'<div class="slsp-item"><div class="slsp-label">Est. Economic Impact</div>'
            f'<div class="slsp-value">{_eco_final}/yr</div></div>'
            f'<div class="slsp-item"><div class="slsp-label">Recommended Priority</div>'
            f'<div class="slsp-value">{_intel["priority"]}</div></div>'
            f'</div></div>'
        )
        st.markdown(summary_html, unsafe_allow_html=True)

    # ── Export & Downloads ────────────────────────────────────────────────────
    st.markdown('<div class="section-header export-header">Export & Downloads</div>', unsafe_allow_html=True)
    _sl_csv      = pivot_tbl.to_csv()
    _monthly_csv = sl[sl["Month"].isin(["January","February","March","April","May","June",
                                         "July","August","September","October","November","December"])].to_csv(index=False)
    _grid_csv    = sl[(sl["Month"] == "Total") & (sl["Grid"].isin(grids_to_show))].to_csv(index=False)
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        st.download_button("↓ Export Data", _sl_csv,
                           "system_loss_annual.csv", "text/csv",
                           use_container_width=True)
    with ec2:
        st.download_button("↓ Export Intelligence Brief", _grid_csv,
                           "system_loss_summary.csv", "text/csv",
                           use_container_width=True)
    with ec3:
        st.download_button("↓ Export Full Report", _monthly_csv,
                           "system_loss_monthly.csv", "text/csv",
                           use_container_width=True)

    # ── Methodology ───────────────────────────────────────────────────
    with st.expander("Methodology & Data Notes", expanded=False):
        st.markdown(
            '<p style="font-size:13px;color:var(--text-secondary);line-height:1.6">'
            '<b>Data Source:</b> NGCP System Loss dataset (annual and monthly). '
            '<b>DOE Mandate:</b> Section 10 of Republic Act 7832 — system loss ceiling of 9.5% for private utilities; '
            'the 2% reference used here reflects the aspired transmission technical loss target. '
            '<b>Economic Impact:</b> Estimated using WESM marginal cost per kWh applied to lost energy volume. '
            '<b>Anomaly Detection:</b> Z-score method — months exceeding ±2σ from the historical seasonal mean are flagged. '
            '<b>Loss Classification:</b> NOMINAL &lt;2% | WATCH 2–3% | ELEVATED 3–5% | CRITICAL &gt;5%.'
            '</p>',
            unsafe_allow_html=True,
        )
