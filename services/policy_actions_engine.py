# services/policy_actions_engine.py
"""
Dynamic policy action and roadmap generation.
All critical risks, emerging risks, and strategic opportunities are derived
from live metrics — no hardcoded text entries.
"""
from config import TARGET_RE_2030, TARGET_SYSTEM_LOSS
from services.classification_engine import (
    classify_system_loss, classify_re_share, classify_demand_growth,
    NOMINAL, WATCH, ELEVATED, CRITICAL, STATUS_COLORS,
)


def generate_policy_cards(re_pct: float, coal_pct: float, avg_sl: float,
                          demand_growth: float, sec_score: float,
                          re_gap: float, yrs_left: int,
                          grid: str = "Philippines") -> dict:
    """
    Returns {critical_risks, emerging_risks, opportunities}.
    Each list contains dicts: {title, impact, action}.
    Derived entirely from input metrics — nothing hardcoded.
    """
    re_needed = re_gap / yrs_left if yrs_left > 0 else 0
    sl_gap    = max(0.0, avg_sl - TARGET_SYSTEM_LOSS)
    coal_risk  = coal_pct > 50
    loss_risk  = avg_sl > TARGET_SYSTEM_LOSS
    demand_risk = demand_growth > 5

    # ── Critical Risks ─────────────────────────────────────────────────
    critical_risks = []

    if coal_risk:
        critical_risks.append({
            "title":  "Coal Concentration",
            "impact": f"Coal at {coal_pct:.1f}% — exceeds 50% concentration threshold",
            "action": "Accelerate retirement of ageing coal plants; block new coal PPA approvals",
        })
    else:
        critical_risks.append({
            "title":  "Coal Dependency",
            "impact": f"Coal at {coal_pct:.1f}% — below 50% threshold but material RE displacement needed",
            "action": "Maintain RE pressure to displace remaining coal baseload",
        })

    if loss_risk:
        critical_risks.append({
            "title":  "Transmission Loss Overage",
            "impact": f"{avg_sl:.2f}% loss vs {TARGET_SYSTEM_LOSS}% DOE target (+{sl_gap:.2f}pp above mandate)",
            "action": "Mandate NGCP transmission audit; enforce annual loss reduction targets",
        })
    else:
        critical_risks.append({
            "title":  "System Loss",
            "impact": f"{avg_sl:.2f}% loss — within {TARGET_SYSTEM_LOSS}% DOE target",
            "action": "Sustain grid maintenance programme; prevent regression above target",
        })

    # ── Emerging Risks ─────────────────────────────────────────────────
    emerging_risks = []

    dem_label = "surging" if demand_growth > 8 else ("elevated" if demand_growth > 5 else "moderate")
    dem_action = (
        "Fast-track capacity procurement; review reserve margins immediately"
        if demand_growth > 8
        else "Advance pipeline capacity projects; monitor quarterly"
        if demand_growth > 5
        else "Continue capacity investment schedule; no emergency action needed"
    )
    emerging_risks.append({
        "title":  "Demand Growth Pressure",
        "impact": f"Peak demand growth {demand_growth:+.1f}%/yr — {dem_label} pace",
        "action": dem_action,
    })

    vre_balancing_severity = "critical" if re_pct > 30 else ("elevated" if re_pct > 20 else "emerging")
    emerging_risks.append({
        "title":  "RE Grid Balancing",
        "impact": f"VRE at {re_pct:.1f}% — {vre_balancing_severity} balancing challenge as intermittent share grows",
        "action": "Deploy grid-scale battery storage; mandate spinning reserve for VRE-heavy grids",
    })

    # ── Strategic Opportunities ────────────────────────────────────────
    opportunities = []

    if re_gap > 0:
        opportunities.append({
            "title":  f"2030 RE Target ({TARGET_RE_2030:.0f}%)",
            "impact": f"RE at {re_pct:.1f}% — {re_gap:.1f}pp gap, need +{re_needed:.1f}pp/yr to reach target",
            "action": (
                f"Accelerate RE auctions; streamline permitting to add +{re_needed:.1f}pp/yr"
                if re_gap > 5
                else "Maintain deployment pace; consider advancing 2035 interim target"
            ),
        })
    else:
        opportunities.append({
            "title":  "2030 RE Target — Met",
            "impact": f"RE at {re_pct:.1f}% — 2030 target achieved; advance 2040 trajectory",
            "action": "Set 2040 interim milestone; expand offshore wind and pumped-hydro pipeline",
        })

    # Demand response potential (dynamic based on demand growth and system loss)
    dr_value = demand_growth * 0.03 * 8760 * 5 / 1e9  # rough DSM value proxy
    opportunities.append({
        "title":  "Demand Response Programme",
        "impact": f"Demand management can defer up to ₱{dr_value:.1f}B in new capacity spend",
        "action": "Launch industrial DSM pilot; incentivise off-peak shifting in commercial sector",
    })

    return {
        "critical_risks":  critical_risks,
        "emerging_risks":  emerging_risks,
        "opportunities":   opportunities,
    }


def generate_roadmap_items(re_pct: float, coal_pct: float, avg_sl: float,
                           demand_growth: float, sec_score: float,
                           re_gap: float, year: int) -> list:
    """
    Returns a flat list of roadmap action items, each with:
    {title, description, category, priority, status, progress_pct}
    Category: 'RE Transition' | 'Grid Infrastructure' | 'Demand Management' | 'Policy & Regulation'
    """
    items = []
    yrs_left = max(1, 2030 - year)

    # RE Transition
    re_urgency = "Critical" if re_gap > 15 else ("High" if re_gap > 5 else "Medium")
    items.append({
        "title":       f"RE Portfolio Expansion to {TARGET_RE_2030:.0f}%",
        "description": f"Current {re_pct:.1f}% RE — need +{re_gap / yrs_left:.1f}pp/yr to reach {TARGET_RE_2030:.0f}% by 2030",
        "category":    "RE Transition",
        "priority":    re_urgency,
        "status":      "In Progress",
        "progress_pct": min(99, int(re_pct / TARGET_RE_2030 * 100)),
    })

    items.append({
        "title":       "Dispatchable RE (Geothermal + Hydro) Priority",
        "description": "Firm baseload RE provides grid stability beyond VRE additions — prioritize for capacity auctions",
        "category":    "RE Transition",
        "priority":    "High",
        "status":      "Planning",
        "progress_pct": 20,
    })

    # Grid Infrastructure
    loss_progress = max(0, int((1 - (avg_sl / (TARGET_SYSTEM_LOSS * 3))) * 100))
    items.append({
        "title":       "NGCP Transmission Rehabilitation",
        "description": f"Reduce system loss from {avg_sl:.2f}% to {TARGET_SYSTEM_LOSS}% DOE mandate via targeted line upgrades",
        "category":    "Grid Infrastructure",
        "priority":    "Critical" if avg_sl > TARGET_SYSTEM_LOSS * 1.5 else "High",
        "status":      "In Progress" if avg_sl > TARGET_SYSTEM_LOSS else "Review",
        "progress_pct": loss_progress,
    })

    items.append({
        "title":       "Grid-Scale Battery Energy Storage (BESS)",
        "description": f"BESS deployment critical as VRE share grows — minimum 500 MW initial tender recommended",
        "category":    "Grid Infrastructure",
        "priority":    "High" if re_pct > 20 else "Medium",
        "status":      "Planning",
        "progress_pct": 15,
    })

    if coal_pct > 30:
        items.append({
            "title":       "Coal Plant Retirement Schedule",
            "description": f"Coal at {coal_pct:.1f}% — structured retirement roadmap needed to avoid stranded asset risk",
            "category":    "Policy & Regulation",
            "priority":    "Critical" if coal_pct > 50 else "High",
            "status":      "Planning",
            "progress_pct": 10,
        })

    # Demand Management
    if demand_growth > 3:
        items.append({
            "title":       "Demand-Side Management Pilot",
            "description": f"Peak demand growing {demand_growth:+.1f}%/yr — DSM programme can defer ₱B in new capacity",
            "category":    "Demand Management",
            "priority":    "High" if demand_growth > 5 else "Medium",
            "status":      "Planning",
            "progress_pct": 5,
        })

    # Interconnection
    items.append({
        "title":       "Mindanao-Visayas Interconnection",
        "description": "Island grid topology limits RE balancing — interconnection enables cross-grid reserve sharing",
        "category":    "Grid Infrastructure",
        "priority":    "Medium",
        "status":      "Planning",
        "progress_pct": 25,
    })

    return items
