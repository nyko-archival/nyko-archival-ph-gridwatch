# utils/icons.py – Lucide SVG icon strings for inline HTML use.
# All icons: viewBox 0 0 24 24, fill none, stroke currentColor, sw=2, round caps/joins.

_BASE = ('xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" '
         'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"')

def svg(paths: str, size: int = 18, color: str = "currentColor", cls: str = "") -> str:
    style = f'color:{color};' if color != "currentColor" else ""
    klass = f' class="{cls}"' if cls else ""
    return (f'<svg {_BASE} width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'style="vertical-align:middle;flex-shrink:0;{style}"{klass}>{paths}</svg>')

# ── path strings ──────────────────────────────────────────────────────────────

_FACTORY       = '<path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M17 18h1"/><path d="M12 18h1"/><path d="M7 18h1"/>'
_ZAP           = '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'
_LEAF          = '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z"/><path d="M2 21c0-3 1.85-5.36 5.08-6"/>'
_ACTIVITY      = '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'
_HEART_PULSE   = '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/><polyline points="3.22 12 9.5 12 10.5 11 12.5 15.5 14.5 8.5 16 12 21.78 12"/>'
_SHIELD_CHECK  = '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>'
_SHIELD_ALERT  = '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M12 8v4"/><path d="M12 16h.01"/>'
_SHIELD_X      = '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m14.5 9-5 5"/><path d="m9.5 9 5 5"/>'
_ALERT_TRI     = '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>'
_TARGET        = '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>'
_RADAR         = '<path d="M19.07 4.93A10 10 0 0 0 6.99 3.34"/><path d="M4 6h.01"/><path d="M2.29 9.62A10 10 0 1 0 21.31 8.35"/><path d="M16.24 7.76A6 6 0 1 0 8.23 16.67"/><path d="M12 18h.01"/><path d="M17.99 11.66A6 6 0 0 1 15.77 16.67"/><circle cx="12" cy="12" r="2"/><path d="m13.41 10.59 5.66-5.66"/>'
_TROPHY        = '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>'
_TRENDING_UP   = '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>'
_ARROW_DOWN    = '<line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>'
_SCALE         = '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21H17"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>'
_ROCKET        = '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>'
_CROWN         = '<path d="m2 4 3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14"/>'
_CLIPBOARD     = '<rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
_ARCHIVE       = '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>'

# ── public icon functions ─────────────────────────────────────────────────────

def factory(size=18, color="currentColor"):      return svg(_FACTORY, size, color)
def zap(size=18, color="currentColor"):          return svg(_ZAP, size, color)
def leaf(size=18, color="currentColor"):         return svg(_LEAF, size, color)
def activity(size=18, color="currentColor"):     return svg(_ACTIVITY, size, color)
def heart_pulse(size=18, color="currentColor"):  return svg(_HEART_PULSE, size, color)
def shield_check(size=18, color="currentColor"): return svg(_SHIELD_CHECK, size, color)
def shield_alert(size=18, color="currentColor"): return svg(_SHIELD_ALERT, size, color)
def shield_x(size=18, color="currentColor"):     return svg(_SHIELD_X, size, color)
def alert_tri(size=18, color="currentColor"):    return svg(_ALERT_TRI, size, color)
def target(size=18, color="currentColor"):       return svg(_TARGET, size, color)
def radar(size=18, color="currentColor"):        return svg(_RADAR, size, color)
def trophy(size=18, color="currentColor"):       return svg(_TROPHY, size, color)
def trending_up(size=18, color="currentColor"):  return svg(_TRENDING_UP, size, color)
def arrow_down(size=18, color="currentColor"):   return svg(_ARROW_DOWN, size, color)
def scale(size=18, color="currentColor"):        return svg(_SCALE, size, color)
def rocket(size=18, color="currentColor"):       return svg(_ROCKET, size, color)
def crown(size=18, color="currentColor"):        return svg(_CROWN, size, color)
def clipboard(size=18, color="currentColor"):    return svg(_CLIPBOARD, size, color)
def archive(size=18, color="currentColor"):      return svg(_ARCHIVE, size, color)

def shield_for_score(score: float, size: int = 20) -> str:
    if score >= 80:   return shield_check(size, "#2dc653")
    if score >= 60:   return shield_alert(size, "#ffd60a")
    if score >= 40:   return shield_x(size, "#f4a261")
    return shield_x(size, "#e63946")
