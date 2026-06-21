# services/intelligence_engine.py
"""
Generates dynamic intelligence text (situation / impact / action / executive summary)
from energy metrics. Views call these functions instead of building inline strings.
"""
from config import TARGET_SYSTEM_LOSS, TARGET_RE_2030
from services.classification_engine import (
    classify_score, classify_system_loss, classify_re_share, classify_demand_growth,
    status_color, NOMINAL, WATCH, ELEVATED, CRITICAL, STATUS_COLORS,
)


def energy_security_intel(avg_score: float, weakest_grid: str, weakest_score: float,
                           worst_comp: str, worst_grid: str) -> dict:
    status = classify_score(avg_score)
    situation = (
        f"National energy security averaged {avg_score:.0f}/100."
    )
    risk = (
        f"{weakest_grid} Grid scored {weakest_score:.0f} — weakest performer this period."
    )
    action = f"Address {worst_comp} deficit in {worst_grid} Grid first."
    return {
        "status": status,
        "color": status_color(status),
        "situation": situation,
        "risk": risk,
        "action": action,
    }


def pillar_note(pillar: str, score: float, re_pct: float, sl_pct: float,
                demand_growth: float) -> str:
    if pillar == "Supply-Demand Balance":
        if score >= 80:
            return "Demand growth within manageable capacity headroom"
        if score >= 60:
            return f"Demand at {demand_growth:.1f}%/yr — approaching capacity ceiling"
        return f"Demand at {demand_growth:.1f}%/yr — capacity adequacy stress elevated"
    elif pillar == "Fuel Diversity Index":
        if score >= 80:
            return "Diversified fuel mix — low concentration risk"
        if score >= 60:
            return f"RE at {re_pct:.1f}% — coal dependence persists"
        return f"Coal-dominant mix — RE at {re_pct:.1f}% vs {TARGET_RE_2030:.0f}% target"
    else:  # Transmission Efficiency
        if score >= 80:
            return f"Loss {sl_pct:.2f}% — within DOE {TARGET_SYSTEM_LOSS}% target"
        if score >= 60:
            return f"Loss {sl_pct:.2f}% — marginally above {TARGET_SYSTEM_LOSS}% target"
        return f"Loss {sl_pct:.2f}% — grid rehabilitation required"


def system_loss_intel(nat_loss: float, grid_vals: dict) -> dict:
    status = classify_system_loss(nat_loss)
    gap = nat_loss - TARGET_SYSTEM_LOSS
    worst_grid = max(grid_vals, key=grid_vals.get) if grid_vals else "N/A"
    worst_val = grid_vals.get(worst_grid, nat_loss)

    situation = (
        f"National system loss at {nat_loss:.2f}%"
        + (f" — {gap:+.2f}pp above DOE {TARGET_SYSTEM_LOSS}% target" if gap > 0
           else f" — within DOE {TARGET_SYSTEM_LOSS}% target")
    )
    if status == CRITICAL:
        impact = f"Severe efficiency loss. {worst_grid} Grid at {worst_val:.2f}% — urgent rehabilitation required."
        action = "Commission immediate NGCP transmission audit; fast-track rehabilitation priority areas"
    elif status == ELEVATED:
        impact = "Above-target losses increasing energy costs and grid inefficiency."
        action = "Mandate annual NGCP transmission efficiency improvement targets"
    elif status == WATCH:
        impact = "Loss marginally above target — monitor quarterly trends."
        action = "Review grid maintenance schedules; investigate seasonal loss patterns"
    else:
        impact = "Transmission efficiency within DOE mandate — sustain performance."
        action = "Continue preventive maintenance programme; maintain loss monitoring cadence"

    return {
        "status": status,
        "color": status_color(status),
        "situation": situation,
        "impact": impact,
        "action": action,
    }


def single_grid_loss_intel(grid: str, g_sl: float, trend_pp: float) -> dict:
    """Grid-specific loss intelligence for single-grid filter mode."""
    status = classify_system_loss(g_sl)
    gap    = g_sl - TARGET_SYSTEM_LOSS

    driver = (
        f"Transmission losses {gap:+.2f}pp above DOE {TARGET_SYSTEM_LOSS}% mandate"
        if gap > 0
        else f"Transmission losses within DOE {TARGET_SYSTEM_LOSS}% mandate"
    )
    if trend_pp > 0.02:
        trend_desc = f"Loss increased {trend_pp:+.3f}pp — worsening efficiency"
    elif trend_pp < -0.02:
        trend_desc = f"Loss decreased {abs(trend_pp):.3f}pp — improving efficiency"
    else:
        trend_desc = f"Loss stable ({trend_pp:+.3f}pp change) — no significant trend"

    if status == CRITICAL:
        risk     = "Severe transmission loss — energy cost impact and grid reliability risk elevated"
        action   = "Commission NGCP transmission audit; fast-track line rehabilitation"
        priority = "Critical"
        impact   = max(0.10, gap * 0.15)
    elif status == ELEVATED:
        risk     = "Continued losses may increase delivered power costs across consumers"
        action   = "Prioritize line upgrades and congestion mitigation"
        priority = "High"
        impact   = max(0.08, gap * 0.12)
    elif status == WATCH:
        risk     = "Loss marginally above DOE target — monitor trend to prevent deterioration"
        action   = "Review maintenance schedules; investigate seasonal loss patterns"
        priority = "Medium"
        impact   = max(0.05, gap * 0.10)
    else:
        risk     = "Grid operating within DOE mandate — sustain efficiency programme"
        action   = "Continue preventive maintenance; maintain monitoring cadence"
        priority = "Low"
        impact   = 0.05

    return {
        "status":     status,
        "color":      status_color(status),
        "driver":     driver,
        "trend":      trend_desc,
        "risk":       risk,
        "action":     action,
        "priority":   priority,
        "impact_est": impact,
    }


def demand_intel(growth_pct: float, grid: str) -> dict:
    status = classify_demand_growth(growth_pct)
    if growth_pct > 8:
        situation = f"{grid} demand surging {growth_pct:.1f}%/yr — above operating bands"
        impact = "Capacity adequacy risk elevated — near-term additions required"
        action = f"Fast-track capacity procurement; review {grid} reserve margin immediately"
    elif growth_pct > 5:
        situation = f"{grid} demand expanding {growth_pct:.1f}%/yr — above sustainable threshold"
        impact = "Plan capacity additions within 18–24 months to avoid shortfall"
        action = "Advance pipeline projects; monitor reserve margins quarterly"
    elif growth_pct >= 0:
        situation = f"{grid} demand growing {growth_pct:.1f}%/yr — within manageable range"
        impact = "Current capacity trajectory adequate for near-term demand"
        action = "Maintain scheduled capacity investments; no emergency action required"
    else:
        situation = f"{grid} demand contracted {abs(growth_pct):.1f}%/yr — reduced capacity pressure"
        impact = "Near-term capacity adequacy comfortable; assess economic drivers"
        action = "Review if contraction is structural or cyclical before deferring investments"

    return {
        "status": status,
        "color": status_color(status),
        "situation": situation,
        "impact": impact,
        "action": action,
    }


def policy_intel(re_pct: float, coal_pct: float, avg_sl: float, re_gap: float,
                 yrs_left: int) -> dict:
    re_needed = re_gap / yrs_left if yrs_left > 0 else 0
    if coal_pct > 50:
        status = CRITICAL
        risk_label = "Coal concentration exceeds 50% threshold"
        action = "Initiate coal retirement legislation immediately"
    elif re_gap > 10:
        status = ELEVATED
        risk_label = "RE trajectory behind 2030 target"
        action = f"Accelerate RE by +{re_needed:.1f}pp/yr to close 2030 gap"
    elif re_gap > 5 or avg_sl > TARGET_SYSTEM_LOSS:
        status = WATCH
        risk_label = "Moderate policy execution gaps"
        action = "Sustain current policy trajectory; focus on execution speed"
    else:
        status = NOMINAL
        risk_label = "Policy trajectory broadly on course"
        action = "Maintain momentum; advance 2040 RE target preparation"

    return {
        "status": status,
        "color": status_color(status),
        "situation": f"RE at {re_pct:.1f}% ({re_gap:.1f}pp below 2030 target); coal at {coal_pct:.1f}%",
        "risk_label": risk_label,
        "action": action,
    }
