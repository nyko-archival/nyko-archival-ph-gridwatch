"""
PH GridWatch – National Energy Command Center
"""
import streamlit as st
import streamlit.components.v1 as _components
import pandas as pd
import os
from datetime import datetime
from pathlib import Path

def load_css(css_file_path: str) -> None:
    try:
        base_dir = Path(__file__).parent
        css_path = base_dir / css_file_path
        if not css_path.exists():
            st.warning(f"CSS file not found at {css_path.resolve()}")
            return
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading CSS: {str(e)}")

st.set_page_config(
    page_title="PH GridWatch",
    page_icon=":material/energy_savings_leaf:",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css("styles.css")  # css-reload-bump 5

from views import (
    Demand, EnergySecurity, Executive, Generation,
    PolicyInsights, Regional, SystemLoss,
)
from config import GRIDS, DATA_DIR
from data_loader import load_generation, load_system_loss, load_hourly_demand_all, load_delivery

_LOADING_MESSAGES = [
    "Analyzing generation portfolio…",
    "Calculating security indicators…",
    "Evaluating transmission performance…",
    "Building executive briefing…",
    "Preparing policy recommendations…",
]

def init_session_state():
    if "data_loaded" not in st.session_state:
        _loader = st.empty()
        _loader.markdown(
            '<div class="ph-loading-screen">'
            '<div class="ph-loading-brand">PH GRIDWATCH</div>'
            '<div class="ph-loading-subtitle">National Energy Intelligence Platform</div>'
            '<div class="ph-loading-status">Loading Intelligence Products…</div>'
            '<div class="ph-loading-bar"><div class="ph-loading-fill"></div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        try:
            st.session_state.gen_df = load_generation()
            st.session_state.sl_df = load_system_loss()
            st.session_state.hourly_df = load_hourly_demand_all()
            st.session_state.delivery_df = load_delivery()
            st.session_state.data_loaded = True
        except Exception as e:
            st.error(f"Failed to load data: {e}")
            st.session_state.gen_df = pd.DataFrame()
            st.session_state.sl_df = pd.DataFrame()
            st.session_state.hourly_df = pd.DataFrame()
            st.session_state.delivery_df = pd.DataFrame()
            st.session_state.data_loaded = False
        finally:
            _loader.markdown(
                '<div class="ph-loading-screen ph-loading-exit">'
                '<div class="ph-loading-brand">PH GRIDWATCH</div>'
                '<div class="ph-loading-subtitle">National Energy Intelligence Platform</div>'
                '<div class="ph-loading-status">Loading Intelligence Products…</div>'
                '<div class="ph-loading-bar"><div class="ph-loading-fill"></div></div>'
                '</div>',
                unsafe_allow_html=True,
            )
            import time; time.sleep(0.35)
            _loader.empty()

    if "global_year" not in st.session_state and not st.session_state.gen_df.empty:
        years = sorted(st.session_state.gen_df["Year"].unique())
        st.session_state.global_year = max(years) if years else 2023
    if "global_grid" not in st.session_state:
        st.session_state.global_grid = "All Grids"

    if "last_updated" not in st.session_state:
        timestamps = []
        for fname in os.listdir(DATA_DIR):
            if fname.endswith(".xlsx"):
                path = os.path.join(DATA_DIR, fname)
                timestamps.append(os.path.getmtime(path))
        if timestamps:
            latest = max(timestamps)
            st.session_state.last_updated = datetime.fromtimestamp(latest).strftime("%Y-%m-%d %H:%M")
        else:
            st.session_state.last_updated = "Unknown"

init_session_state()

if "page" not in st.session_state:
    st.session_state.page = "Executive"

_NAV_PAGES = ["Executive", "Demand", "Generation", "System Loss", "Regional", "Energy Security", "Policy"]

with st.sidebar:
    # ── Brand ──────────────────────────────────────────────────────
    st.markdown(
        '<div class="sb-brand">'
        '<div class="sb-brand-name">PH GridWatch <span class="sb-brand-ver">v4.0</span></div>'
        '<div class="sb-brand-sub">National Energy Intelligence Platform</div>'
        '<div class="sb-brand-author">By Nyko Archival</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Filters ────────────────────────────────────────────────────
    if not st.session_state.gen_df.empty:
        years = sorted(st.session_state.gen_df["Year"].unique())
        st.selectbox("Year", years, index=years.index(st.session_state.global_year),
                     key="global_year_widget", label_visibility="visible")
        st.session_state.global_year = st.session_state.global_year_widget

        grid_opts = ["All Grids"] + GRIDS
        idx = grid_opts.index(st.session_state.global_grid) if st.session_state.global_grid in grid_opts else 0
        st.selectbox("Grid", grid_opts, index=idx, key="global_grid_widget",
                     label_visibility="visible")
        st.session_state.global_grid = st.session_state.global_grid_widget

    # ── Navigation: st.button() with primary/secondary type for active state ─
    st.markdown('<div class="sb-nav-label">Navigation</div>', unsafe_allow_html=True)
    for _p in _NAV_PAGES:
        _is_active = (_p == st.session_state.page)
        if st.button(
            _p,
            key=f"nav_btn_{_p}",
            use_container_width=True,
            type="primary" if _is_active else "secondary",
        ):
            st.session_state.page = _p
            st.rerun()

    # ── Late-injected CSS ──────────────────────────────────────────────
    st.markdown("""<style>
/* Selectbox compact */
[data-testid="stSidebar"] [data-baseweb="select"]>div{min-height:32px!important;height:32px!important;padding:0 10px!important;border-radius:6px!important;}
[data-testid="stSidebar"] [data-baseweb="select"]>div>div{min-height:32px!important;font-size:12px!important;font-weight:600!important;line-height:32px!important;padding:0!important;}
[data-testid="stSidebar"] [data-baseweb="select"] svg{width:12px!important;height:12px!important;}
[data-testid="stSidebar"] label,[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{font-size:9px!important;font-weight:700!important;text-transform:uppercase!important;letter-spacing:1px!important;margin-bottom:3px!important;}

/* ── Nav buttons: base reset ── */
[data-testid="stSidebar"] [data-testid^="stBaseButton"]{
    background:transparent!important;
    border:none!important;
    border-left:2px solid transparent!important;
    border-radius:0 4px 4px 0!important;
    padding:0 12px!important;
    height:36px!important;min-height:36px!important;
    text-align:left!important;justify-content:flex-start!important;
    font-size:12.5px!important;font-weight:400!important;
    color:rgba(150,168,185,0.6)!important;
    box-shadow:none!important;outline:none!important;
    width:100%!important;
    transition:background .15s,color .15s,border-color .15s!important;
}
[data-testid="stSidebar"] [data-testid^="stBaseButton"] p{
    font-size:12.5px!important;font-weight:inherit!important;
    color:inherit!important;text-transform:none!important;letter-spacing:normal!important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover{
    background:rgba(255,255,255,0.05)!important;
    color:rgba(210,225,240,0.9)!important;
    border-left-color:rgba(0,102,255,0.4)!important;
}
/* ── Active nav button (primary type) ── */
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]{
    background:rgba(0,102,255,0.1)!important;
    color:#dce8ff!important;
    font-weight:600!important;
    border-left:3px solid #0066FF!important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover{
    background:rgba(0,102,255,0.15)!important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:focus,
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:focus{
    box-shadow:none!important;outline:none!important;
}

/* Element wrapper spacing */
[data-testid="stSidebar"] .element-container{margin-bottom:0!important;padding:0!important;}
[data-testid="stSidebar"] [data-testid="stSelectbox"]{margin-bottom:4px!important;}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"]{min-height:14px!important;margin-bottom:0!important;}
</style>""", unsafe_allow_html=True)

    # ── Hide BaseWeb select search input via MutationObserver ─────
    _components.html("""<script>
(function(){
  function hideSelectSearch(){
    // BaseWeb renders the open-dropdown in a portal on document.body.
    // The search input sits inside [data-baseweb="popover"] or the
    // listbox container. Hide every input inside those containers.
    var targets = document.querySelectorAll(
      '[data-baseweb="popover"] input, [role="listbox"] input, [data-baseweb="menu"] input'
    );
    targets.forEach(function(el){
      var row = el.closest('[data-baseweb="input"]') || el.parentElement;
      if(row){ row.style.cssText='display:none!important'; }
      el.style.cssText='display:none!important';
    });
  }
  var obs = new MutationObserver(hideSelectSearch);
  obs.observe(document.body, {childList:true, subtree:true});
  hideSelectSearch();
})();
</script>""", height=0, scrolling=False)

    # ── Footer ─────────────────────────────────────────────────────
    _pg   = st.session_state.get("page", "Executive")
    _grid = st.session_state.get("global_grid", "All Grids")
    _yr   = st.session_state.get("global_year", "—")
    _upd  = st.session_state.get("last_updated", "—")
    _components.html(f"""
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#000;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}}
.ft{{border-top:1px solid rgba(255,255,255,0.08);padding-top:5px;margin-top:2px;}}
.row{{display:flex;justify-content:space-between;align-items:baseline;margin-top:3px;}}
.k{{font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:0.7px;color:rgba(122,143,166,0.65);white-space:nowrap;}}
.v{{font-size:9px;font-weight:500;color:rgba(122,143,166,0.8);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.hi{{color:rgba(168,184,200,0.9);font-weight:600;}}
</style>
<div class="ft">
<div class="row"><span class="k">View</span><span class="v hi">{_pg}</span></div>
<div class="row"><span class="k">Grid</span><span class="v hi">{_grid}</span></div>
<div class="row"><span class="k">Year</span><span class="v hi">{_yr}</span></div>
<div class="row"><span class="k">Sources</span><span class="v">NGCP · DOE · ERC</span></div>
<div class="row"><span class="k">Updated</span><span class="v">{_upd}</span></div>
</div>
""", height=90, scrolling=False)

page_routing = {
    "Executive": Executive.show,
    "Demand": Demand.show,
    "Generation": Generation.show,
    "System Loss": SystemLoss.show,
    "Regional": Regional.show,
    "Energy Security": EnergySecurity.show,
    "Policy": PolicyInsights.show,
}
page_routing[st.session_state.page]()