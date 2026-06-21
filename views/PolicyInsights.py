# views/PolicyInsights.py
import streamlit as st
import pandas as pd
from config import TARGET_RE_2030, TARGET_SYSTEM_LOSS, RENEWABLE_TYPES
from utils.icons import alert_tri, radar, target as icon_target, rocket, crown, clipboard, archive
from components.ui import render_intel_summary
from services.intelligence_engine import policy_intel
from services.policy_actions_engine import generate_policy_cards, generate_roadmap_items

_STATUS_BADGE = {
    "In Progress": "badge-in-progress",
    "Planning":    "badge-planning",
    "Review":      "badge-review",
    "Pending":     "badge-pending",
    "Approved":    "badge-approved",
}

_PRIORITY_BADGE = {
    "Critical": "badge-critical",
    "High":     "badge-high",
    "Medium":   "badge-medium",
    "Low":      "badge-low",
}

def _badge(text, badge_map):
    cls = badge_map.get(text, "badge-low")
    return f'<span class="roadmap-badge {cls}">{text}</span>'

def _progress(pct):
    return f'''<div class="progress-bar-wrap">
        <div class="progress-bar-fill" style="width:{pct}%"></div>
    </div>'''

def show():
    st.markdown(
        '<h1>Policy Intelligence</h1>'
        '<div class="page-description">Strategic intelligence for national energy policy makers and executives</div>',
        unsafe_allow_html=True,
    )

    gen = st.session_state.gen_df
    sl  = st.session_state.sl_df
    if gen.empty:
        st.error("Data not available.")
        return

    year    = st.session_state.global_year
    gen_yr  = gen[gen["Year"] == year]
    tot_gen = gen_yr["Generation_MWh"].sum()
    re_pct  = (gen_yr[gen_yr["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
               / tot_gen * 100 if tot_gen > 0 else 0)
    coal_pct = (gen_yr[gen_yr["PlantType"] == "Coal"]["Generation_MWh"].sum()
                / tot_gen * 100 if tot_gen > 0 else 0)
    avg_sl  = (sl[(sl["Year"] == year) & (sl["Grid"] == "Philippines") & (sl["Month"] == "Total")]["SystemLoss_pct"].mean()
               if not sl.empty else 0) or 0

    re_gap    = max(0, TARGET_RE_2030 - re_pct)
    sl_gap    = max(0, avg_sl - TARGET_SYSTEM_LOSS)
    yrs_left  = max(1, 2030 - year)
    re_needed = re_gap / yrs_left if yrs_left > 0 else 0

    # ── Policy Scenario Lab (in-page) ────────────────────────────────
    _SCENARIOS = [
        ("Baseline",       0.0, 0.0, 0.00, "No policy acceleration"),
        ("Conservative",   0.5, 0.5, 0.10, "Modest adjustments"),
        ("Balanced",       1.5, 1.0, 0.30, "Steady acceleration"),
        ("Aggressive",     3.0, 2.0, 0.60, "Strong intervention"),
        ("Transformative", 5.0, 3.0, 1.00, "Maximum policy ambition"),
    ]

    if "policy_scenario" not in st.session_state:
        st.session_state.policy_scenario = "Baseline"

    # Inject compact styling for scenario pill buttons (reliable fallback beyond :has())
    st.markdown(
        '<style>'
        '.slp-scenario-row .stButton button {'
        '  height:30px!important;min-height:30px!important;'
        '  padding:0 10px!important;font-size:9px!important;'
        '  font-weight:800!important;letter-spacing:1px!important;'
        '  text-transform:uppercase!important;border-radius:4px!important;'
        '  background:rgba(10,18,35,0.5)!important;'
        '  border:1px solid rgba(30,43,71,0.9)!important;'
        '  color:rgba(142,159,175,0.6)!important;}'
        '.slp-scenario-row .stButton button[kind="primary"]{'
        '  background:rgba(0,102,255,0.15)!important;'
        '  border:1px solid rgba(96,165,250,0.45)!important;'
        '  color:#60A5FA!important;}'
        '</style>',
        unsafe_allow_html=True,
    )

    # Two-column: label left | buttons right — balanced single-row layout
    _slp_l, _slp_r = st.columns([1, 3.2], gap="small")

    with _slp_l:
        st.markdown(
            '<span class="slp-outer-marker"></span>'
            '<div class="slp-label-col">'
            '<div class="slp-title">⚗ Policy Scenario Lab</div>'
            '<div class="slp-subtitle">Model policy interventions to project 2030 energy outcomes</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with _slp_r:
        st.markdown('<div class="slp-scenario-row">', unsafe_allow_html=True)
        _btn_cols = st.columns(5, gap="small")
        for i, (sc_name, *_rest) in enumerate(_SCENARIOS):
            with _btn_cols[i]:
                is_active = st.session_state.policy_scenario == sc_name
                if st.button(sc_name, key=f"sc_{sc_name}", use_container_width=True,
                             type="primary" if is_active else "secondary"):
                    st.session_state.policy_scenario = sc_name
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    _active = next(s for s in _SCENARIOS if s[0] == st.session_state.policy_scenario)
    _, re_accel, coal_phase, loss_cut, _sc_desc = _active

    if st.session_state.policy_scenario != "Baseline":
        st.markdown(
            f'<div class="slp-active-strip">'
            f'<span class="slp-active-name">{st.session_state.policy_scenario}</span>'
            f'<span class="slp-sep">·</span>'
            f'<span class="slp-active-desc">{_sc_desc}</span>'
            f'<span class="slp-sep">·</span>'
            f'RE <span class="slp-pos">+{re_accel:.1f}pp/yr</span>'
            f'<span class="slp-sep">·</span>'
            f'Coal <span class="slp-neg">−{coal_phase:.1f}pp/yr</span>'
            f'<span class="slp-sep">·</span>'
            f'Loss <span class="slp-pos">−{loss_cut:.2f}pp/yr</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    scenario_active = st.session_state.policy_scenario != "Baseline"

    # Scenario projections
    re_scenario_2030 = min(100.0, re_pct + (re_needed + re_accel) * yrs_left)
    coal_scenario_2030 = max(0.0, coal_pct - coal_phase * yrs_left)
    loss_scenario_2030 = max(0.0, avg_sl - loss_cut * yrs_left)
    re_gap_scenario = max(0.0, TARGET_RE_2030 - re_scenario_2030)

    # ── Page Intelligence Summary ─────────────────────────────────────
    _pi = policy_intel(re_pct, coal_pct, avg_sl, re_gap, yrs_left)
    _sc_suffix = (f" [{st.session_state.get('policy_scenario', 'Baseline')} scenario active]"
                  if scenario_active else "")
    render_intel_summary(
        situation=_pi["situation"] + _sc_suffix,
        impact=f'{_pi["status"]}: {_pi["risk_label"]}',
        action=_pi["action"],
        impact_status=_pi["status"],
        tag="Policy Intel",
    )

    # ── 3-column policy cards (dynamic via policy_actions_engine) ────
    st.markdown('<div class="section-header">Intelligence Assessment</div>', unsafe_allow_html=True)
    _dem_growth = 0.0
    if not st.session_state.hourly_df.empty:
        _hdf = st.session_state.hourly_df
        _yrs = sorted(_hdf["Year"].unique())
        if year in _yrs and (year - 1) in _yrs:
            _cur = _hdf[_hdf["Year"] == year]["DailyAvg_MW"].mean()
            _prv = _hdf[_hdf["Year"] == (year - 1)]["DailyAvg_MW"].mean()
            _dem_growth = (_cur - _prv) / _prv * 100 if _prv > 0 else 0.0

    from utils.calculations import compute_energy_security_score
    _sec_score, *_ = compute_energy_security_score(re_pct, _dem_growth, avg_sl)
    _pcards = generate_policy_cards(
        re_pct=re_pct, coal_pct=coal_pct, avg_sl=avg_sl,
        demand_growth=_dem_growth, sec_score=_sec_score,
        re_gap=re_gap, yrs_left=yrs_left,
    )

    col1, col2, col3 = st.columns(3)
    _ic_crit = "#EF4444"
    _ic_emrg = "#F59E0B"
    _ic_opp  = "#2DC653"

    def _card_items_html(items):
        html = ""
        for item in items[:2]:
            html += (
                f'<div class="policy-item">'
                f'<div class="policy-item-title">{item["title"]}</div>'
                f'<div class="policy-item-impact">{item["impact"]}</div>'
                f'<div class="policy-item-action">→ {item["action"]}</div>'
                f'</div>'
            )
        return html

    with col1:
        card_html = (
            f'<div class="policy-card critical">'
            f'<div class="policy-card-title">{alert_tri(16, _ic_crit)} Critical Risks</div>'
            + _card_items_html(_pcards["critical_risks"])
            + f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

    with col2:
        card_html = (
            f'<div class="policy-card emerging">'
            f'<div class="policy-card-title">{radar(16, _ic_emrg)} Emerging Risks</div>'
            + _card_items_html(_pcards["emerging_risks"])
            + f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

    with col3:
        card_html = (
            f'<div class="policy-card opportunity">'
            f'<div class="policy-card-title">{icon_target(16, _ic_opp)} Strategic Opportunities</div>'
            + _card_items_html(_pcards["opportunities"])
            + f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

    # ── Policy Priority Matrix ────────────────────────────────────────
    st.markdown('<div class="section-header">Policy Priority Matrix</div>', unsafe_allow_html=True)
    st.caption("2×2 matrix: Impact (national energy security benefit) vs Implementation Difficulty. Prioritise Quick Wins first.")
    _rkt = rocket(14, "#2DC653")
    _crw = crown(14, "#60A5FA")
    _clp = clipboard(14, "#F59E0B")
    _arc = archive(14, "#64748B")
    matrix_html = (
        '<div class="policy-matrix-wrapper">'
        '<div class="matrix-cell qw">'
        '<div class="matrix-cell-hd">'
        '<div class="matrix-quad-label">High Impact<br>Easy to Execute</div>'
        f'<span class="matrix-tag qw">{_rkt} Quick Wins</span>'
        '</div>'
        '<ul class="matrix-items">'
        '<li>Streamline solar/wind permit processing</li>'
        '<li>Expand net-metering for commercial rooftops</li>'
        '<li>DSM programme for large industrial users</li>'
        '</ul>'
        '</div>'
        '<div class="matrix-cell str">'
        '<div class="matrix-cell-hd">'
        '<div class="matrix-quad-label">High Impact<br>Complex Execution</div>'
        f'<span class="matrix-tag str">{_crw} Strategic</span>'
        '</div>'
        '<ul class="matrix-items">'
        '<li>Mindanao–Visayas submarine interconnection</li>'
        '<li>Grid-scale BESS procurement (&gt;500 MW)</li>'
        '<li>Coal asset retirement roadmap legislation</li>'
        '</ul>'
        '</div>'
        '<div class="matrix-cell fi">'
        '<div class="matrix-cell-hd">'
        '<div class="matrix-quad-label">Lower Impact<br>Easy to Execute</div>'
        f'<span class="matrix-tag fi">{_clp} Fill-Ins</span>'
        '</div>'
        '<ul class="matrix-items">'
        '<li>EV charging station policy update</li>'
        '<li>Smart meter rollout (residential)</li>'
        '<li>Energy efficiency labelling programme</li>'
        '</ul>'
        '</div>'
        '<div class="matrix-cell dep">'
        '<div class="matrix-cell-hd">'
        '<div class="matrix-quad-label">Lower Impact<br>Complex Execution</div>'
        f'<span class="matrix-tag dep">{_arc} Deprioritise</span>'
        '</div>'
        '<ul class="matrix-items">'
        '<li>Hydrogen pilot (pre-commercial, long lead)</li>'
        '<li>Nuclear feasibility study expansion</li>'
        '<li>Full sector restructuring proposals</li>'
        '</ul>'
        '</div>'
        '</div>'
    )
    st.markdown(matrix_html, unsafe_allow_html=True)

    # ── National Energy Outlook ───────────────────────────────────────
    _forecast_year = year + 2
    st.markdown(f'<div class="section-header">National Energy Outlook — {_forecast_year} Forecast</div>', unsafe_allow_html=True)
    re_2026 = min(re_pct + re_needed, 100)
    re_2026_gap = max(0, TARGET_RE_2030 - re_2026)

    all_years = sorted(gen["Year"].unique())
    if len(all_years) >= 2:
        prev_yr_gen = gen[gen["Year"] == all_years[-2]]["Generation_MWh"].sum()
        curr_yr_gen = tot_gen
        demand_growth = ((curr_yr_gen / prev_yr_gen) - 1) * 100 if prev_yr_gen > 0 else 3.5
    else:
        demand_growth = 3.5

    projected_gen = tot_gen * (1 + demand_growth / 100)
    on_track = re_2026_gap < 5.0

    # Scenario-adjusted outlook values
    _re_display     = re_scenario_2030 if scenario_active else re_2026
    _gap_display    = re_gap_scenario  if scenario_active else re_2026_gap
    _loss_display   = loss_scenario_2030 if scenario_active else avg_sl
    _on_track_disp  = _gap_display < 5.0
    _scenario_label = f" [Scenario: +{re_accel:.1f}pp/yr RE, -{coal_phase:.1f}pp/yr coal, -{loss_cut:.2f}pp/yr loss]" if scenario_active else ""

    _re_color    = '#2DC653' if _re_display >= 30 else '#F59E0B'
    _gap_color   = '#2DC653' if _on_track_disp else '#EF4444'
    _loss_color  = '#2DC653' if _loss_display <= TARGET_SYSTEM_LOSS else ('#F59E0B' if _loss_display < TARGET_SYSTEM_LOSS + 0.5 else '#EF4444')
    _re_label    = "Scenario" if scenario_active else "Forecast"
    _loss_label  = "Scenario" if scenario_active else "Outlook"
    _re_sub      = f"Target: {TARGET_RE_2030:.0f}% by 2030{'  ▲ scenario' if scenario_active else ''}"
    _gap_sub     = 'On track ✓' if _on_track_disp else 'Intervention needed'
    _loss_sub    = f"{'Scenario projected' if scenario_active else 'System loss'} by {_forecast_year}"
    _scenario_note = (
        '<div style="font-size:10px;color:#F59E0B;margin-top:8px;padding:4px 8px;'
        'background:rgba(245,158,11,0.06);border-radius:4px">'
        'Scenario mode active — projections reflect selected policy intervention</div>'
        if scenario_active else ''
    )
    outlook_html = (
        f'<div class="outlook-panel">'
        f'<div class="outlook-header">{_forecast_year} Projection — Based on {year} Trajectory{_scenario_label}</div>'
        f'<div class="outlook-grid">'
        f'<div class="outlook-metric">'
        f'<div class="outlook-label">Projected Generation</div>'
        f'<div class="outlook-value">{projected_gen/1e6:.1f} <span style="font-size:13px">TWh</span></div>'
        f'<div class="outlook-sub">+{demand_growth:.1f}% YoY growth</div>'
        f'</div>'
        f'<div class="outlook-metric">'
        f'<div class="outlook-label">{_re_label} RE Share</div>'
        f'<div class="outlook-value" style="color:{_re_color}">{_re_display:.1f}<span style="font-size:13px">%</span></div>'
        f'<div class="outlook-sub">{_re_sub}</div>'
        f'</div>'
        f'<div class="outlook-metric">'
        f'<div class="outlook-label">2030 RE Gap</div>'
        f'<div class="outlook-value" style="color:{_gap_color}">{_gap_display:.1f}<span style="font-size:13px">pp</span></div>'
        f'<div class="outlook-sub">{_gap_sub}</div>'
        f'</div>'
        f'<div class="outlook-metric">'
        f'<div class="outlook-label">{_loss_label} Loss</div>'
        f'<div class="outlook-value" style="color:{_loss_color}">{_loss_display:.2f}<span style="font-size:13px">%</span></div>'
        f'<div class="outlook-sub">{_loss_sub}</div>'
        f'</div>'
        f'</div>'
        + _scenario_note
        + f'</div>'
    )
    st.markdown(outlook_html, unsafe_allow_html=True)

    # ── Enhanced Policy Roadmap (dynamic) ────────────────────────────
    st.markdown('<div class="section-header">Policy Action Roadmap 2025–2030</div>', unsafe_allow_html=True)

    _roadmap_items = generate_roadmap_items(
        re_pct=re_pct, coal_pct=coal_pct, avg_sl=avg_sl,
        demand_growth=_dem_growth, sec_score=_sec_score,
        re_gap=re_gap, year=year,
    )

    rows_html = ""
    for r in _roadmap_items:
        rows_html += (
            f'<tr>'
            f'<td style="color:var(--text-primary);font-weight:600">{r["title"]}</td>'
            f'<td style="color:#8E9FAF;font-size:11px">{r["category"]}</td>'
            f'<td>{_badge(r["priority"], _PRIORITY_BADGE)}</td>'
            f'<td>{_badge(r["status"], _STATUS_BADGE)}</td>'
            f'<td>{_progress(r["progress_pct"])}</td>'
            f'</tr>'
        )

    table_html = (
        '<table class="roadmap-table">'
        '<thead><tr>'
        '<th>Action</th><th>Category</th><th>Priority</th><th>Status</th><th>Progress</th>'
        '</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
    )
    st.markdown(table_html, unsafe_allow_html=True)

    # ── Export & Downloads ────────────────────────────────────────────────────
    st.markdown('<div class="section-header export-header">Export & Downloads</div>', unsafe_allow_html=True)
    _roadmap_csv = pd.DataFrame(_roadmap_items).to_csv(index=False)
    _kpi_csv = pd.DataFrame([{
        "Year": year, "RE_pct": round(re_pct, 2), "Coal_pct": round(coal_pct, 2),
        "System_Loss_pct": round(avg_sl, 3), "RE_Gap_2030_pp": round(re_gap, 2),
        "RE_Needed_per_yr_pp": round(re_needed, 2), "Years_to_2030": yrs_left,
    }]).to_csv(index=False)
    _all_cards = (
        [{"category": "Critical Risk", **c} for c in _pcards.get("critical_risks", [])] +
        [{"category": "Emerging Risk", **c} for c in _pcards.get("emerging_risks", [])] +
        [{"category": "Opportunity",   **c} for c in _pcards.get("opportunities",  [])]
    )
    _policy_cards_csv = pd.DataFrame(_all_cards).to_csv(index=False) if _all_cards else ""
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        st.download_button("↓ Export Data", _kpi_csv,
                           f"policy_kpis_{year}.csv", "text/csv",
                           use_container_width=True)
    with ec2:
        st.download_button("↓ Export Intelligence Brief", _policy_cards_csv,
                           f"policy_intelligence_{year}.csv", "text/csv",
                           use_container_width=True)
    with ec3:
        st.download_button("↓ Export Full Report", _roadmap_csv,
                           f"policy_roadmap_{year}.csv", "text/csv",
                           use_container_width=True)

    # ── Methodology ───────────────────────────────────────────────────
    with st.expander("Methodology & Data Notes", expanded=False):
        st.markdown(
            '<p style="font-size:13px;color:var(--text-secondary);line-height:1.6">'
            '<b>Policy Cards:</b> Generated dynamically from current-year energy data thresholds. '
            'Critical risks are triggered when RE &lt; 20%, system loss &gt; 5%, or security score &lt; 40. '
            '<b>Scenario Lab:</b> Each scenario applies annual percentage-point adjustments to RE share, coal share, '
            'and system loss, compounded over years remaining to 2030. '
            '<b>Roadmap:</b> Policy actions are prioritized by gap severity and estimated implementation timeframe. '
            '<b>Data basis:</b> DOE Generation, NGCP System Loss, and DOE Delivery datasets.'
            '</p>',
            unsafe_allow_html=True,
        )
