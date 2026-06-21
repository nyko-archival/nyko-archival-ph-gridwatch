# components/ui.py
"""
Shared UI components for PH GridWatch — National Energy Intelligence Platform.

All render_* functions call st.markdown() directly. All *_html() helpers
return raw HTML strings for embedding inside larger HTML blocks.
"""
import streamlit as st

# ── Status vocabulary (single source of truth) ──────────────────────────────

_STATUS_MAP = {
    "NOMINAL":  ("#10B981", "rgba(16,185,129,0.15)",  "rgba(16,185,129,0.35)"),
    "WATCH":    ("#F59E0B", "rgba(245,158,11,0.15)",   "rgba(245,158,11,0.35)"),
    "ELEVATED": ("#F59E0B", "rgba(245,158,11,0.15)",   "rgba(245,158,11,0.35)"),
    "CRITICAL": ("#EF4444", "rgba(239,68,68,0.15)",    "rgba(239,68,68,0.35)"),
}

_STATUS_ALIASES = {
    # Legacy labels normalised to 4-level system
    "NOMINAL": "NOMINAL", "GROWING": "NOMINAL", "SECURE": "NOMINAL",
    "GOOD": "NOMINAL", "ON TRACK": "NOMINAL", "LOW RISK": "NOMINAL",
    "WATCH": "WATCH", "MODERATE": "WATCH", "ELEVATED": "WATCH",
    "MODERATE RISK": "WATCH",
    "HIGH RISK": "CRITICAL", "CRITICAL": "CRITICAL",
}


def normalise_status(raw: str) -> str:
    """Normalise any legacy status label to NOMINAL/WATCH/ELEVATED/CRITICAL."""
    upper = raw.upper().strip()
    if upper in _STATUS_MAP:
        return upper
    return _STATUS_ALIASES.get(upper, "WATCH")


def status_color(status: str) -> str:
    """Return the hex colour for a given status."""
    s = normalise_status(status)
    return _STATUS_MAP.get(s, _STATUS_MAP["WATCH"])[0]


def status_badge_html(status: str, size: str = "sm") -> str:
    """Return a styled status badge HTML span."""
    s = normalise_status(status)
    color, bg, border = _STATUS_MAP.get(s, _STATUS_MAP["WATCH"])
    fs = "9px" if size == "sm" else "11px"
    return (
        f'<span class="status-badge" '
        f'style="background:{bg};color:{color};border-color:{border};font-size:{fs}">'
        f'{s}</span>'
    )


# ── Page-level components ────────────────────────────────────────────────────

def render_page_header(title: str, description: str, marker_class: str = "") -> None:
    """Render the standard page h1 + description bar."""
    mc = f" {marker_class}" if marker_class else ""
    st.markdown(
        f'<h1>{title}</h1>'
        f'<div class="page-description{mc}">{description}</div>',
        unsafe_allow_html=True,
    )


def render_section_header(text: str) -> None:
    """Render a standardised section header."""
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


def render_intel_summary(
    situation: str,
    impact: str,
    action: str,
    impact_status: str = None,
    tag: str = "Intelligence",
) -> None:
    """
    Render the page-level intelligence summary bar (Situation / Impact / Action).

    impact_status: optional NOMINAL/WATCH/ELEVATED/CRITICAL — colours the Impact text.

    Uses flat single-line string concatenation to avoid Python-Markdown treating
    indented HTML as a code block (4+ spaces after a blank line = code block).
    """
    color_style = f'style="color:{status_color(impact_status)}"' if impact_status else ""
    html = (
        f'<div class="page-intel-summary">'
        f'<span class="pis-tag">{tag}</span>'
        f'<div class="pis-block">'
        f'<span class="pis-block-label">Situation</span>'
        f'<span class="pis-block-text">{situation}</span>'
        f'</div>'
        f'<div class="pis-block">'
        f'<span class="pis-block-label">Impact</span>'
        f'<span class="pis-block-text" {color_style}>{impact}</span>'
        f'</div>'
        f'<div class="pis-block">'
        f'<span class="pis-block-label">Recommended Action</span>'
        f'<span class="pis-block-text">{action}</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ── KPI card ─────────────────────────────────────────────────────────────────

def render_kpi_card(
    col,
    label: str,
    value: str,
    sub: str = "",
    status: str = None,
    commentary: str = None,
    value_color: str = None,
) -> None:
    """
    Render a standardised KPI card into a Streamlit column.

    label       – uppercase metric name
    value       – formatted metric value (string)
    sub         – small caption below the value
    status      – optional NOMINAL/WATCH/ELEVATED/CRITICAL badge
    commentary  – optional 1-line interpretation shown below value
    value_color – optional hex override for the value colour
    """
    badge_html = status_badge_html(status) if status else ""
    commentary_html = (
        f'<div class="kpi-card-commentary">{commentary}</div>'
        if commentary else ""
    )
    v_style = f'style="color:{value_color}"' if value_color else ""
    col.markdown(f"""<div class="kpi-card">
      <div class="kpi-card-header">
        <span class="kpi-card-label">{label}</span>
        {badge_html}
      </div>
      <div class="kpi-card-value-container">
        <span class="kpi-card-value" {v_style}>{value}</span>
      </div>
      {commentary_html}
      <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)


# ── Empty state ───────────────────────────────────────────────────────────────

def render_empty_state(message: str = "No data available for the selected filters.") -> None:
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:center;
        min-height:120px;border:1px solid rgba(30,43,71,0.5);border-radius:8px;
        color:#62748C;font-size:13px;letter-spacing:0.3px;
        background:rgba(7,13,25,0.5);text-align:center;padding:24px">
        {message}
    </div>
    """, unsafe_allow_html=True)


# ── Export section ────────────────────────────────────────────────────────────

def render_export_section(downloads: list) -> None:
    """
    downloads: list of (label, data_bytes_or_str, filename, mime) tuples.
    Renders a uniform export row.
    """
    render_section_header("Export")
    st.markdown('<div class="export-card-container">', unsafe_allow_html=True)
    cols = st.columns(len(downloads))
    for i, (label, data, filename, mime) in enumerate(downloads):
        with cols[i]:
            st.download_button(label, data, filename, mime, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ── Methodology section ───────────────────────────────────────────────────────

def render_methodology_section(items: list) -> None:
    """
    items: list of (title_str, body_str) tuples.
    Renders a collapsible methodology expander.
    """
    with st.expander("Methodology & Data Notes"):
        for title, body in items:
            st.markdown(f"**{title}**")
            st.caption(body)


# ── Smart number formatting helpers ──────────────────────────────────────────

def fmt_peso(value_pesos: float, decimals: int = 1) -> str:
    """Format a peso amount with smart B/M/K suffix. Never returns ₱0.0B."""
    if value_pesos >= 1e9:
        return f"₱{value_pesos / 1e9:.{decimals}f}B"
    if value_pesos >= 1e6:
        return f"₱{value_pesos / 1e6:.0f}M"
    if value_pesos >= 1e3:
        return f"₱{value_pesos / 1e3:.0f}K"
    if value_pesos > 0:
        return f"< ₱1K"
    return "₱0"


def fmt_mwh(value_mwh: float) -> str:
    """Format MWh with smart TWh/GWh/MWh suffix."""
    if value_mwh >= 1e6:
        return f"{value_mwh / 1e6:.2f} TWh"
    if value_mwh >= 1e3:
        return f"{value_mwh / 1e3:.1f} GWh"
    return f"{value_mwh:,.0f} MWh"
