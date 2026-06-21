# services/classification_engine.py
"""
Single source of truth for all NOMINAL / WATCH / ELEVATED / CRITICAL
status classifications. Views import from here — no inline thresholds.
"""
from config import TARGET_SYSTEM_LOSS, TARGET_RE_2030

NOMINAL   = "NOMINAL"
WATCH     = "WATCH"
ELEVATED  = "ELEVATED"
CRITICAL  = "CRITICAL"

STATUS_COLORS = {
    NOMINAL:  "#10B981",
    WATCH:    "#D97706",
    ELEVATED: "#EA580C",
    CRITICAL: "#DC2626",
}

STATUS_BG = {
    NOMINAL:  "rgba(16,185,129,0.15)",
    WATCH:    "rgba(217,119,6,0.15)",
    ELEVATED: "rgba(234,88,12,0.15)",
    CRITICAL: "rgba(220,38,38,0.15)",
}

STATUS_BORDER = {
    NOMINAL:  "rgba(16,185,129,0.35)",
    WATCH:    "rgba(217,119,6,0.35)",
    ELEVATED: "rgba(234,88,12,0.35)",
    CRITICAL: "rgba(220,38,38,0.35)",
}


def status_color(status: str) -> str:
    return STATUS_COLORS.get(status, STATUS_COLORS[WATCH])


def status_attrs(status: str) -> tuple:
    """Return (color, badge_bg, border_rgba) for a given status."""
    return (
        STATUS_COLORS.get(status, STATUS_COLORS[WATCH]),
        STATUS_BG.get(status, STATUS_BG[WATCH]),
        STATUS_BORDER.get(status, STATUS_BORDER[WATCH]),
    )


# ── Domain classifiers ────────────────────────────────────────────────────────

def classify_score(score: float) -> str:
    """Classify a 0-100 score: ≥80 NOMINAL, ≥60 WATCH, ≥40 ELEVATED, else CRITICAL."""
    if score >= 80:
        return NOMINAL
    if score >= 60:
        return WATCH
    if score >= 40:
        return ELEVATED
    return CRITICAL


def classify_system_loss(loss_pct: float) -> str:
    """≤2.00%=NOMINAL  2.01–2.25%=WATCH  2.26–3.00%=ELEVATED  >3.00%=CRITICAL"""
    if loss_pct <= 2.00:
        return NOMINAL
    if loss_pct <= 2.25:
        return WATCH
    if loss_pct <= 3.00:
        return ELEVATED
    return CRITICAL


SYSTEM_LOSS_THRESHOLDS = {
    NOMINAL:  "≤ 2.00% — within DOE mandate",
    WATCH:    "2.01–2.25% — marginally above target",
    ELEVATED: "2.26–3.00% — above target",
    CRITICAL: "> 3.00% — critical overage",
}


def classify_re_share(re_pct: float) -> str:
    gap = TARGET_RE_2030 - re_pct
    if gap <= 0:
        return NOMINAL
    if gap < 5:
        return WATCH
    if gap < 15:
        return ELEVATED
    return CRITICAL


def classify_demand_growth(growth_pct: float) -> str:
    if growth_pct > 8:
        return ELEVATED
    if growth_pct > 5:
        return WATCH
    if growth_pct >= -2:
        return NOMINAL
    return WATCH


def classify_operational_health(score: float) -> str:
    if score >= 85:
        return NOMINAL
    if score >= 70:
        return WATCH
    if score >= 55:
        return ELEVATED
    return CRITICAL


def classify_risk_index(risk: float) -> str:
    if risk < 35:
        return NOMINAL
    if risk < 60:
        return WATCH
    return CRITICAL
