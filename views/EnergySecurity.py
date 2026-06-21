# views/EnergySecurity.py
"""Energy Security Dashboard – custom Energy Security Score, score cards, radar chart."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from config import GRIDS, COLORS, RENEWABLE_TYPES, TARGET_RE_2030, TARGET_SYSTEM_LOSS
from utils.calculations import compute_energy_security_score, compute_growth_rate
from utils.icons import shield_for_score


def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _status_for_score(score):
    """Returns (status_label, color, badge_bg, border_rgba) for NOMINAL/WATCH/ELEVATED/CRITICAL."""
    if score >= 80:
        return "NOMINAL",   "#10B981", "rgba(16,185,129,0.15)",  "rgba(16,185,129,0.35)"
    if score >= 60:
        return "WATCH",     "#F59E0B", "rgba(245,158,11,0.15)",  "rgba(245,158,11,0.35)"
    if score >= 40:
        return "ELEVATED",  "#F59E0B", "rgba(245,158,11,0.15)",  "rgba(245,158,11,0.35)"
    return     "CRITICAL",  "#EF4444", "rgba(239,68,68,0.15)",   "rgba(239,68,68,0.35)"


def _pillar_color(score):
    if score >= 80: return "#10B981"
    if score >= 60: return "#F59E0B"
    if score >= 40: return "#F59E0B"
    return "#EF4444"


def _pillar_status_label(score):
    if score >= 80: return "NOMINAL"
    if score >= 60: return "WATCH"
    if score >= 40: return "ELEVATED"
    return "CRITICAL"


# Tooltip on every Demand Growth indicator — prevents the label being misread as
# supply adequacy. The proxy sees demand-side trend only; rotational brownouts are a
# supply/reserve-margin event this dataset cannot observe.
DEMAND_GROWTH_TIP = (
    "Observed year-on-year demand-growth trend only. "
    "Does NOT reflect reserve margin, plant availability, or supply adequacy — "
    "it cannot capture rotational brownouts or supply-side shortfalls."
)


def _demand_growth_class(growth_pct):
    """Classify the observed demand-growth trend — the actual input behind the
    Supply-Demand Balance Proxy. Reported as a trend (not a verdict on supply),
    with neutral/cool colours so a flat trend never reads as an 'all-clear' on
    supply adequacy. Higher growth = more demand-side pressure on capacity.
    """
    if growth_pct < 1.0: return "FLAT",    "#94A3B8"   # slate — neutral, not "good"
    if growth_pct < 3.5: return "RISING",  "#38BDF8"   # cyan — informational
    if growth_pct < 6.0: return "HIGH",    "#F59E0B"   # amber
    return "SURGING", "#EF4444"                          # red


def _pillar_note(pillar, score, r):
    re_pct = r.get("RE_pct_scenario", r.get("RE_pct_original", 0))
    sl_pct = r.get("SysLoss_scenario", r.get("SysLoss_original", 0))
    g = r.get("DemandGrowth", 0)
    if pillar == "Supply-Demand Balance Proxy":
        if score >= 80: return "Demand growth within manageable capacity headroom"
        if score >= 60: return f"Demand at {g:.1f}%/yr — approaching capacity ceiling"
        return f"Demand at {g:.1f}%/yr — capacity adequacy stress elevated"
    elif pillar == "Fuel Diversity Index":
        if score >= 80: return "Diversified fuel mix — low concentration risk"
        if score >= 60: return f"RE at {re_pct:.1f}% — coal dependence persists"
        return f"Coal-dominant mix — RE at {re_pct:.1f}% vs {TARGET_RE_2030}% target"
    else:  # Transmission Efficiency
        if score >= 80: return f"Loss {sl_pct:.2f}% — within DOE {TARGET_SYSTEM_LOSS}% target"
        if score >= 60: return f"Loss {sl_pct:.2f}% — marginally above {TARGET_SYSTEM_LOSS}% target"
        return f"Loss {sl_pct:.2f}% — grid rehabilitation required"


def score_card(g, r, scenario_active):
    score = r["Score"]
    status, color, badge_bg, border_rgba = _status_for_score(score)

    # Primary driver = weakest pillar
    pillar_scores = {
        "Supply-Demand Balance Proxy": r["Adequacy"],
        "Fuel Diversity Index":  r["Diversity"],
        "Transmission Efficiency": r["Efficiency"],
    }
    primary_driver = min(pillar_scores, key=pillar_scores.get)
    re_pct = r["RE_pct_scenario"] if scenario_active else r["RE_pct_original"]
    sl_pct = r["SysLoss_scenario"] if scenario_active else r["SysLoss_original"]

    if primary_driver == "Supply-Demand Balance Proxy":
        key_risk = f"Demand surge {r['DemandGrowth']:+.1f}%/yr"
        action = "Expand capacity additions pipeline"
    elif primary_driver == "Fuel Diversity Index":
        gap = max(0.0, TARGET_RE_2030 - re_pct)
        key_risk = f"RE at {re_pct:.1f}% — {gap:.1f}pp below 2030 target"
        action = "Accelerate dispatchable RE deployment"
    else:
        key_risk = f"System loss {sl_pct:.2f}% vs {TARGET_SYSTEM_LOSS}% target"
        action = "Prioritize grid rehabilitation programme"

    scenario_html = ""
    if scenario_active:
        scenario_html = (
            f'<div class="ssc-scenario">Scenario: RE {r["RE_pct_original"]:.1f}'
            f'→{r["RE_pct_scenario"]:.1f}%&nbsp;|&nbsp;'
            f'Loss {r["SysLoss_original"]:.2f}→{r["SysLoss_scenario"]:.2f}%</div>'
        )

    shield_icon = shield_for_score(score, size=20)
    intel_inner = (
        f'<div class="ssc-intel-item">'
        f'<span class="ssc-intel-label">Primary Driver</span>'
        f'<span class="ssc-intel-value">{primary_driver}</span>'
        f'</div>'
        f'<div class="ssc-intel-item">'
        f'<span class="ssc-intel-label">Key Risk</span>'
        f'<span class="ssc-intel-value" style="color:{color}">{key_risk}</span>'
        f'</div>'
        f'<div class="ssc-intel-item">'
        f'<span class="ssc-intel-label">Recommended Action</span>'
        f'<span class="ssc-intel-value">{action}</span>'
        f'</div>'
    )
    dp_label, dp_color = _demand_growth_class(r["DemandGrowth"])
    pillars_inner = (
        f'<div class="ssc-pillar" title="{DEMAND_GROWTH_TIP}">'
        f'<span class="ssc-pillar-label">Demand Growth</span>'
        f'<span class="ssc-pillar-chip" style="color:{dp_color};'
        f'border-color:{dp_color}40;background:{dp_color}1a">{dp_label}</span>'
        f'</div>'
        f'<div class="ssc-pillar">'
        f'<span class="ssc-pillar-label">Fuel Diversity</span>'
        f'<span class="ssc-pillar-val">{r["Diversity"]:.0f}</span>'
        f'</div>'
        f'<div class="ssc-pillar">'
        f'<span class="ssc-pillar-label">Transmission Eff.</span>'
        f'<span class="ssc-pillar-val">{r["Efficiency"]:.0f}</span>'
        f'</div>'
    )
    return (
        f'<div class="security-score-card" style="border-top-color:{color}">'
        f'<div class="ssc-grid-name">{shield_icon} {g} Grid</div>'
        f'<div class="ssc-score" style="color:{color}">{score:.0f}</div>'
        f'<div class="ssc-status-badge" style="background:{badge_bg};color:{color};border-color:{border_rgba}">{status}</div>'
        f'<div class="ssc-divider"></div>'
        f'<div class="ssc-intel">{intel_inner}</div>'
        + scenario_html
        + f'<div class="ssc-pillars">{pillars_inner}</div>'
        f'</div>'
    )


def show():
    grid = st.session_state.global_grid
    _national_mode = (grid == "All Grids")
    if _national_mode:
        _page_title = "Energy Security Dashboard"
        _page_desc  = "National energy security assessment — supply-demand balance proxy, fuel diversity, and transmission efficiency"
    else:
        _page_title = f"{grid} Grid Energy Security"
        _page_desc  = f"{grid} grid energy security analysis — supply-demand balance, fuel diversity, and transmission efficiency"

    st.markdown(
        f'<h1>{_page_title}</h1>'
        f'<div class="page-description energy-security-page-marker">{_page_desc}</div>',
        unsafe_allow_html=True,
    )

    gen = st.session_state.gen_df
    sl  = st.session_state.sl_df
    hourly = st.session_state.hourly_df
    if gen.empty or sl.empty or hourly.empty:
        st.error("Required data missing.")
        return

    year = st.session_state.global_year
    # grid and _national_mode already set above

    scenario_active = not _national_mode
    if scenario_active:
        st.markdown(
            '<div class="es-scenario-panel">'
            '<div class="es-scenario-title">⚙ Scenario Analysis</div>'
            '<div class="es-scenario-sub">Simulate policy interventions to project grid security outcomes</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        _es_l, _es_r = st.columns(2, gap="large")
        with _es_l:
            st.markdown('<span class="es-slider-marker"></span>', unsafe_allow_html=True)
            re_adjust = st.slider(
                "RE Share Adjustment (pp)", -10, 10, 0,
                help="Simulate higher/lower renewable penetration")
        with _es_r:
            loss_reduction = st.slider(
                "System Loss Reduction (pp)", -2, 2, 0,
                help="Negative = improvement (lower loss)")
    else:
        re_adjust = 0
        loss_reduction = 0

    # ── Compute scores for all grids ─────────────────────────────────
    results = {}
    grids_to_evaluate = GRIDS if grid == "All Grids" else [grid]
    for g in grids_to_evaluate:
        g_gen = gen[(gen["Grid"] == g) & (gen["Year"] == year)]
        tot = g_gen["Generation_MWh"].sum()
        re  = g_gen[g_gen["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
        re_pct = re / tot * 100 if tot > 0 else 0
        re_pct_scenario = max(0.0, re_pct + re_adjust)

        d = hourly[hourly["Grid"] == g]
        if not d.empty:
            cur_avg  = d[d["Year"] == year]["DailyAvg_MW"].mean()
            prev_avg = d[d["Year"] == (year - 1)]["DailyAvg_MW"].mean() \
                       if (year - 1) in d["Year"].values else cur_avg
            growth = compute_growth_rate(cur_avg, prev_avg) if prev_avg > 0 else 2.0
        else:
            growth = 2.0

        sl_row  = sl[(sl["Grid"] == g) & (sl["Year"] == year) & (sl["Month"] == "Total")]
        sl_pct  = sl_row["SystemLoss_pct"].mean() if not sl_row.empty else 2.5
        sl_pct_scenario = max(0.0, sl_pct - loss_reduction)

        score, adq, div, eff = compute_energy_security_score(
            re_pct_scenario, growth, sl_pct_scenario)
        results[g] = {
            "Score": score, "Adequacy": adq, "Diversity": div, "Efficiency": eff,
            "RE_pct_original": re_pct, "RE_pct_scenario": re_pct_scenario,
            "DemandGrowth": growth,
            "SysLoss_original": sl_pct, "SysLoss_scenario": sl_pct_scenario,
        }

    # ── Page Intelligence Summary ─────────────────────────────────────
    if results:
        avg_score = sum(r["Score"] for r in results.values()) / len(results)
        weakest_grid = min(results, key=lambda g: results[g]["Score"])
        weakest_score = results[weakest_grid]["Score"]
        _, summ_color, _, _ = _status_for_score(avg_score)

        # Most limiting component across all grids
        worst_comp_val = 999.0
        worst_comp_name = "—"
        worst_comp_grid = "—"
        for g_name, r in results.items():
            for cname, cval in [
                ("Supply-Demand Balance Proxy", r["Adequacy"]),
                ("Fuel Diversity", r["Diversity"]),
                ("Transmission Efficiency", r["Efficiency"]),
            ]:
                if cval < worst_comp_val:
                    worst_comp_val = cval
                    worst_comp_name = cname
                    worst_comp_grid = g_name

        if _national_mode:
            n = len(results)
            situation_txt = f"National energy security averaged {avg_score:.0f}/100 across {n} grids."
            risk_txt = f"{weakest_grid} Grid scored {weakest_score:.0f} — weakest performer this period."
            action_txt = f"Address {worst_comp_name} deficit in {worst_comp_grid} Grid first."
        else:
            r_single = results[grid]
            status_lbl = _status_for_score(r_single["Score"])[0]
            situation_txt = f"{grid} Grid scores {r_single['Score']:.0f}/100 — {status_lbl}."
            risk_txt = f"{worst_comp_name} is the primary constraint at {worst_comp_val:.0f}/100."
            action_txt = (
                "Accelerate dispatchable RE deployment" if worst_comp_name == "Fuel Diversity"
                else "Expand capacity additions pipeline" if worst_comp_name == "Supply-Demand Balance Proxy"
                else "Prioritize grid rehabilitation programme"
            )

        summ_html = (
            f'<div class="page-intel-summary">'
            f'<span class="pis-tag">{"National Intel" if _national_mode else grid + " Intel"}</span>'
            f'<div class="pis-block">'
            f'<span class="pis-block-label">Situation</span>'
            f'<span class="pis-block-text">{situation_txt}</span>'
            f'</div>'
            f'<div class="pis-block">'
            f'<span class="pis-block-label">Key Risk</span>'
            f'<span class="pis-block-text" style="color:{summ_color}">{risk_txt}</span>'
            f'</div>'
            f'<div class="pis-block">'
            f'<span class="pis-block-label">Priority Action</span>'
            f'<span class="pis-block-text">{action_txt}</span>'
            f'</div>'
            f'</div>'
        )
        st.markdown(summ_html, unsafe_allow_html=True)

    # ── Score Cards ───────────────────────────────────────────────────
    _sec_header = "Energy Security Score" if not _national_mode else "Energy Security Score by Grid"
    st.markdown(f'<div class="section-header">{_sec_header}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="es-model-note">'
        '<b>Model scope:</b> scores derive from demand-growth, fuel-mix, and transmission-loss '
        'data only. They <b>exclude real-time reserve margin and plant availability</b>, so they do '
        '<b>not</b> capture supply-side events such as NGCP rotational brownouts — a grid can show a '
        'flat demand trend while still under supply stress.'
        '</div>',
        unsafe_allow_html=True,
    )

    if len(results) == 1:
        g_name = list(results.keys())[0]
        r_single = results[g_name]
        col_card, col_detail = st.columns([2, 3])
        with col_card:
            st.markdown(score_card(g_name, r_single, scenario_active), unsafe_allow_html=True)
        with col_detail:
            # Grid-specific breakdown panel
            _adq, _div, _eff = r_single["Adequacy"], r_single["Diversity"], r_single["Efficiency"]
            _pillars = [
                ("Supply-Demand Balance Proxy", _adq,
                 f"Demand growth {r_single['DemandGrowth']:+.1f}%/yr"),
                ("Fuel Diversity Index", _div,
                 f"RE {r_single['RE_pct_original']:.1f}% vs {TARGET_RE_2030}% target"),
                ("Transmission Efficiency", _eff,
                 f"System loss {r_single['SysLoss_original']:.2f}%"),
            ]
            rows = ""
            for pname, pval, psub in _pillars:
                if pname == "Supply-Demand Balance Proxy":
                    disp_name = "Demand Growth"
                    status_txt, pc = _demand_growth_class(r_single["DemandGrowth"])
                else:
                    disp_name = pname
                    pc = _pillar_color(pval)
                    status_txt = f"{_pillar_status_label(pval)} — {pval:.0f}/100"
                rows += (
                    f'<div class="sec-pillar-row">'
                    f'<span class="sec-pillar-row-label">{disp_name}</span>'
                    f'<span class="sec-pillar-row-status" style="color:{pc}">{status_txt}</span>'
                    f'<span class="sec-pillar-row-note">{psub}</span>'
                    f'</div>'
                )
            weakest = min(_pillars, key=lambda x: x[1])
            w_color = _pillar_color(weakest[1])
            w_disp = "Demand Growth" if weakest[0] == "Supply-Demand Balance Proxy" else weakest[0]
            detail_html = (
                f'<div class="sec-radar-intel" style="margin-top:0">'
                f'<div class="sec-radar-intel-title">{g_name} Grid — Pillar Breakdown</div>'
                + rows +
                f'<div class="sec-priority-row">'
                f'<div class="sec-priority-label">Priority Focus</div>'
                f'<div class="sec-priority-value" style="color:{w_color}">{w_disp}</div>'
                f'<div class="sec-pillar-row-note" style="margin-top:4px">'
                f'Score {weakest[1]:.0f}/100 — address this pillar first</div>'
                f'</div></div>'
            )
            st.markdown(detail_html, unsafe_allow_html=True)
    else:
        cols = st.columns(3)
        for i, g_name in enumerate(GRIDS):
            if g_name in results:
                with cols[i]:
                    st.markdown(score_card(g_name, results[g_name], scenario_active),
                                unsafe_allow_html=True)

    # ── Component Breakdown — Executive Table ────────────────────────
    st.markdown('<div class="section-header">Executive Security Assessment</div>',
                unsafe_allow_html=True)
    st.caption(
        "Supply-Demand Balance Proxy uses demand growth rate as a proxy (not actual reserve margin). "
        "Fuel Diversity Index = RE share index. Transmission Efficiency = inverse of system loss."
    )
    _PILLAR_NAMES = [
        ("Supply-Demand Balance Proxy", "Adequacy"),
        ("Fuel Diversity Index",  "Diversity"),
        ("Transmission Efficiency", "Efficiency"),
    ]
    comp_rows = []
    for g_name, r in results.items():
        weakest_pillar = min(_PILLAR_NAMES, key=lambda x: r[x[1]])
        wname = weakest_pillar[0]
        wval  = r[weakest_pillar[1]]
        if wname == "Supply-Demand Balance Proxy":
            pri_action = f"Expand capacity pipeline (demand {r['DemandGrowth']:+.1f}%/yr)"
        elif wname == "Fuel Diversity Index":
            gap = max(0, TARGET_RE_2030 - r["RE_pct_original"])
            pri_action = f"Accelerate dispatchable RE (+{gap:.1f}pp gap to target)"
        else:
            pri_action = f"Grid rehabilitation (loss {r['SysLoss_original']:.2f}% vs {TARGET_SYSTEM_LOSS}% target)"

        comp_rows.append({
            "Grid":             g_name,
            "Score":            f"{r['Score']:.0f}",
            "Status":           _status_for_score(r["Score"])[0],
            "Primary Weakness": f"{wname} ({wval:.0f}/100)",
            "Priority Action":  pri_action,
            "RE Share":         f"{r['RE_pct_original']:.1f}%",
            "System Loss":      f"{r['SysLoss_original']:.2f}%",
            "Demand Growth":    f"{r['DemandGrowth']:+.1f}%/yr",
        })
    df_comp = pd.DataFrame(comp_rows)
    st.dataframe(df_comp, use_container_width=True, hide_index=True)
    st.download_button(
        "Download security assessment as CSV",
        df_comp.to_csv(index=False),
        "energy_security_assessment.csv", "text/csv"
    )

    # ── Radar Chart + Security Intelligence ──────────────────────────
    st.markdown('<div class="section-header">Multi-Dimension Radar Comparison</div>',
                unsafe_allow_html=True)

    col_radar, col_intel = st.columns([3, 2])

    with col_radar:
        st.caption(
            "Three-pillar comparison. Supply-Demand Balance Proxy is a demand-growth proxy "
            "— not actual reserve margin. Scores of 80+ = NOMINAL."
        )
        categories = ["Supply-Demand<br>Balance Proxy", "Fuel Diversity<br>Index", "Transmission<br>Efficiency"]
        fig_radar = go.Figure()
        for g_name, r in results.items():
            vals = [r["Adequacy"], r["Diversity"], r["Efficiency"]]
            vals += [vals[0]]
            trace_color = COLORS[g_name]
            fig_radar.add_trace(go.Scatterpolar(
                r=vals,
                theta=categories + [categories[0]],
                fill="toself",
                fillcolor=hex_to_rgba(trace_color, 0.16),
                name=g_name,
                line=dict(color=trace_color, width=2.5),
                marker=dict(color=trace_color, size=6),
                opacity=0.78,
            ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor="rgba(7,13,25,0.75)",
                domain=dict(x=[0.05, 0.95], y=[0.0, 1.0]),
                radialaxis=dict(
                    range=[0, 100],
                    tickfont=dict(color="#8E9FAF", size=13),
                    gridcolor="rgba(248,250,252,0.18)",
                    linecolor="rgba(248,250,252,0.30)",
                    angle=90,
                    tickvals=[20, 40, 60, 80, 100],
                ),
                angularaxis=dict(
                    tickfont=dict(color="#F8FAFC", size=14),
                    gridcolor="rgba(248,250,252,0.15)",
                    linecolor="rgba(248,250,252,0.30)",
                ),
            ),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                font=dict(color="#F8FAFC", size=13),
                orientation="h", y=-0.04, x=0.5,
                xanchor="center", yanchor="top",
            ),
            height=420,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    with col_intel:
        # Average pillar scores across evaluated grids
        avg_adq = sum(r["Adequacy"]  for r in results.values()) / len(results)
        avg_div = sum(r["Diversity"] for r in results.values()) / len(results)
        avg_eff = sum(r["Efficiency"] for r in results.values()) / len(results)

        avg_r = {
            "Adequacy": avg_adq, "Diversity": avg_div, "Efficiency": avg_eff,
            "RE_pct_original": sum(r["RE_pct_original"] for r in results.values()) / len(results),
            "SysLoss_original": sum(r["SysLoss_original"] for r in results.values()) / len(results),
            "DemandGrowth": sum(r["DemandGrowth"] for r in results.values()) / len(results),
        }

        pillar_data = [
            ("Supply-Demand Balance Proxy", avg_adq, "Demand Growth"),
            ("Fuel Diversity Index",  avg_div, "Fuel Diversity Index"),
            ("Transmission Efficiency", avg_eff, "Transmission Efficiency"),
        ]
        weakest_p = min(pillar_data, key=lambda x: x[1])

        rows_html = ""
        for pillar_key, pillar_val, pillar_display in pillar_data:
            p_note  = _pillar_note(pillar_key, pillar_val, avg_r)
            if pillar_key == "Supply-Demand Balance Proxy":
                status_txt, p_color = _demand_growth_class(avg_r["DemandGrowth"])
            else:
                p_color = _pillar_color(pillar_val)
                status_txt = f"{_pillar_status_label(pillar_val)} — {pillar_val:.0f}/100"
            rows_html += (
                f'<div class="sec-pillar-row">'
                f'<span class="sec-pillar-row-label">{pillar_display}</span>'
                f'<span class="sec-pillar-row-status" style="color:{p_color}">{status_txt}</span>'
                f'<span class="sec-pillar-row-note">{p_note}</span>'
                f'</div>'
            )

        w_color = _pillar_color(weakest_p[1])
        priority_html = (
            f'<div class="sec-priority-row">'
            f'<div class="sec-priority-label">Most Concerning Metric</div>'
            f'<div class="sec-priority-value" style="color:{w_color}">{weakest_p[2]}</div>'
            f'<div class="sec-pillar-row-note" style="margin-top:4px">'
            f'Score {weakest_p[1]:.0f}/100 — address this pillar first for fastest security gains'
            f'</div>'
            f'</div>'
        )
        intel_panel_html = (
            '<div class="sec-radar-intel">'
            '<div class="sec-radar-intel-title">Security Intelligence</div>'
            + rows_html
            + priority_html
            + '</div>'
        )
        st.markdown(intel_panel_html, unsafe_allow_html=True)

    # ── Historical Trend ──────────────────────────────────────────────
    st.markdown('<div class="section-header">Historical Energy Security Score Trend</div>',
                unsafe_allow_html=True)
    st.caption(
        "Annual score evolution per grid. Colored bands show classification thresholds. "
        "NOMINAL ≥80 | WATCH 60–79 | ELEVATED 40–59 | CRITICAL <40."
    )
    hist = []
    for yr in sorted(gen["Year"].unique()):
        for g_name in grids_to_evaluate:
            g_gen = gen[(gen["Grid"] == g_name) & (gen["Year"] == yr)]
            tot = g_gen["Generation_MWh"].sum()
            re  = g_gen[g_gen["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
            re_pct = re / tot * 100 if tot > 0 else 0
            sl_row = sl[(sl["Grid"] == g_name) & (sl["Year"] == yr) & (sl["Month"] == "Total")]
            sl_pct = sl_row["SystemLoss_pct"].mean() if not sl_row.empty else 2.5
            s, *_ = compute_energy_security_score(re_pct, 3.0, sl_pct)
            hist.append({"Year": yr, "Grid": g_name, "Score": s})

    hist_df = pd.DataFrame(hist)
    fig_hist = px.line(
        hist_df, x="Year", y="Score", color="Grid",
        color_discrete_map=COLORS, markers=True,
        template="plotly_dark", range_y=[0, 100],
    )
    for lo, hi, lbl, col in [
        (80, 100, "NOMINAL",   "#10B981"),
        (60,  80, "WATCH",     "#F59E0B"),
        (40,  60, "ELEVATED",  "#F59E0B"),
        ( 0,  40, "CRITICAL",  "#EF4444"),
    ]:
        fig_hist.add_hrect(y0=lo, y1=hi, fillcolor=col, opacity=0.055, line_width=0,
                           annotation_text=lbl, annotation_position="right",
                           annotation_font_color=col, annotation_font_size=10)
    fig_hist.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=320, legend_title_text="",
        margin=dict(l=0, r=72, t=8, b=0),
    )
    st.plotly_chart(fig_hist, use_container_width=True)

    # ── Export & Downloads ────────────────────────────────────────────────────
    st.markdown('<div class="section-header export-header">Export & Downloads</div>', unsafe_allow_html=True)
    _score_csv = df_comp.to_csv(index=False)
    _hist_csv  = hist_df.to_csv(index=False)
    _full_csv  = pd.DataFrame([
        {"Grid": g, "Year": year, **{k: v for k, v in r.items() if k != "RE_pct_scenario" and k != "SysLoss_scenario"}}
        for g, r in results.items()
    ]).to_csv(index=False)
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        st.download_button("↓ Export Data", _score_csv,
                           f"energy_security_{year}.csv", "text/csv",
                           use_container_width=True)
    with ec2:
        st.download_button("↓ Export Intelligence Brief", _full_csv,
                           f"security_assessment_{year}.csv", "text/csv",
                           use_container_width=True)
    with ec3:
        st.download_button("↓ Export Full Report", _hist_csv,
                           "security_score_history.csv", "text/csv",
                           use_container_width=True)

    # ── Methodology ───────────────────────────────────────────────────
    with st.expander("Methodology & Data Notes", expanded=False):
        st.markdown(
            '<p style="font-size:13px;color:var(--text-secondary);line-height:1.6">'
            '<b>Energy Security Score:</b> Weighted composite of three pillars scored 0–100 — '
            'Supply-Demand Balance Proxy (40%), Fuel Diversity Index (40%), Transmission Efficiency (20%). '
            '<b>Supply-Demand Balance Proxy (Adequacy):</b> Inverse of demand growth rate — higher growth reduces score. '
            'Note: this is a demand-growth proxy, not an actual reserve margin calculation. '
            '<b>Fuel Diversity Index (Diversity):</b> RE share as a percentage of the 50% maximum target. '
            '<b>Transmission Efficiency (Efficiency):</b> Inverse of system loss rate, benchmarked at the 2% DOE target. '
            '<b>Thresholds:</b> NOMINAL ≥80 | WATCH 60–79 | ELEVATED 40–59 | CRITICAL &lt;40.'
            '</p>',
            unsafe_allow_html=True,
        )
