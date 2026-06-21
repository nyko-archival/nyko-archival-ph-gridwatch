# views/Executive.py
"""Executive Dashboard – National Energy Command Center"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
from shapely.geometry import shape
from shapely.ops import transform
import pyproj
from config import GRIDS, RENEWABLE_TYPES, TARGET_RE_2030, TARGET_RE_2040, TARGET_SYSTEM_LOSS
from utils.icons import factory, zap, leaf, activity, heart_pulse, shield_check, alert_tri
from utils.calculations import (compute_energy_security_score,
    generate_briefing, gen_commentary, demand_commentary, health_commentary, sec_commentary,
    forecast_annual_peak, forecast_re_trajectory)
from services.classification_engine import classify_operational_health, STATUS_COLORS

# ---------- Regional mapping helpers (unchanged) ----------
REGION_MAPPING = {
    "Autonomous Region in Muslim Mindanao": "Autonomous Region in Muslim Mindanao",
    "Bangsamoro Autonomous Region in Muslim Mindanao": "Autonomous Region in Muslim Mindanao",
    "BICOL REGION": "Bicol",
    "CALABARZON": "Calabarzon",
    "CARAGA": "Caraga",
    "CENTRAL VISAYAS": "Central Visayas",
    "Cagayan Valley": "Cagayan Valley",
    "Central Luzon": "Central Luzon",
    "Cordillera Administrative Region": "Cordillera Administrative Region",
    "DAVAO REGION": "Davao",
    "EASTERN VISAYAS": "Eastern Visayas",
    "Ilocos Region": "Ilocos",
    "NCR": "National Capital Region",
    "NORTHERN MINDANAO": "Northern Mindanao",
    "Soccskargen": "Soccsksargen",
    "Soccsksargen": "Soccsksargen",
    "WESTERN VISAYAS": "Western Visayas",
    "ZAMBOANGA PENINSULA": "Zamboanga Peninsula",
    "Mimaropa": "Mimaropa",
}
EXCLUDE_REGIONS = {
    "TOTAL PHILIPPINES", "Total Philippines", "North Luzon", "South Luzon",
    "Non-Meralco", "Luzon", "Visayas", "Mindanao", "Negros Island Region",
    "Negros Island", None, ""
}
GRID_TO_REGIONS = {
    "Luzon": ["Ilocos", "Cagayan Valley", "Central Luzon", "Calabarzon", "Mimaropa",
              "Bicol", "National Capital Region", "Cordillera Administrative Region"],
    "Visayas": ["Western Visayas", "Central Visayas", "Eastern Visayas"],
    "Mindanao": ["Zamboanga Peninsula", "Northern Mindanao", "Davao", "Soccsksargen",
                 "Caraga", "Autonomous Region in Muslim Mindanao"]
}

def extract_name_in_parentheses(name: str) -> str:
    if not isinstance(name, str): return ""
    start = name.find("("); end = name.find(")")
    if start != -1 and end != -1: return name[start+1:end].strip()
    return name.strip()

def normalise_region_name(name: str) -> str:
    if not isinstance(name, str): return None
    inner = extract_name_in_parentheses(name)
    if inner in REGION_MAPPING: return REGION_MAPPING[inner]
    if name in REGION_MAPPING: return REGION_MAPPING[name]
    norm = inner.title()
    if norm.endswith(" Region"): norm = norm[:-7]
    if "Bangsamoro" in norm: return "Autonomous Region in Muslim Mindanao"
    return norm

def compute_centroid(geometry):
    try:
        geom = shape(geometry)
        project = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32651', always_xy=True).transform
        geom_metric = transform(project, geom)
        centroid_metric = geom_metric.centroid
        project_back = pyproj.Transformer.from_crs('EPSG:32651', 'EPSG:4326', always_xy=True).transform
        centroid = transform(project_back, centroid_metric)
        return centroid.y, centroid.x
    except Exception:
        return None, None

@st.cache_data
def load_geojson_and_mapping(filepath="ph_regions.json"):
    try:
        with open(filepath, "r") as f:
            geojson = json.load(f)
        mapping = {}
        centroids = {}
        for feature in geojson["features"]:
            name = feature["properties"].get("name", "")
            if not name: continue
            region_key = name.strip()
            lat, lon = compute_centroid(feature["geometry"])
            if lat is not None and lon is not None:
                centroids[region_key] = (lat, lon)
            mapping[region_key] = feature
        return geojson, mapping, centroids
    except Exception as e:
        st.warning(f"Could not load GeoJSON: {e}")
        return None, None, None

def kpi_card(label, value, unit, trend_ctx, trend_pct, status_text, commentary, icon_svg=""):
    trend_class = "positive" if trend_pct >= 0 else "negative"
    trend_symbol = "▲" if trend_pct >= 0 else "▼"
    trend_html = f'<span class="kpi-trend {trend_class}">{trend_symbol} {abs(trend_pct):.1f}%</span>' if trend_pct != 0 else '<span class="kpi-trend">—</span>'
    su = status_text.upper()
    if su in ("NOMINAL", "GROWING", "SECURE", "LOW RISK", "ON TRACK", "GOOD"):
        status_class = "success"
    elif su in ("WATCH", "MODERATE", "ELEVATED", "MODERATE RISK"):
        status_class = "warning"
    else:
        status_class = "danger"
    label_html = (f'<span class="kpi-icon-wrap">{icon_svg}</span>{label}' if icon_svg else label)
    return f"""<div class="kpi-card kpi-card--exec">
      <div class="kpi-card-header">
        <span class="kpi-card-label">{label_html}</span>
        <span class="status-badge status-{status_class}">{status_text}</span>
      </div>
      <div class="kpi-card-value-container">
        <span class="kpi-card-value">{value}</span>
        <span class="kpi-card-unit">{unit}</span>
      </div>
      <div class="kpi-card-commentary">{commentary}</div>
      <div class="kpi-card-trend-container">{trend_html}<span class="kpi-card-context">{trend_ctx}</span></div>
    </div>"""

def show():
    gen = st.session_state.gen_df
    sl = st.session_state.sl_df
    delivery = st.session_state.delivery_df
    hourly = st.session_state.hourly_df

    if gen.empty or sl.empty:
        st.error("Core energy data not available.")
        return

    layers = ["Generation (MWh)", "Demand (MW)", "Delivery (MWh)", "System Loss (%)", "RE Share (%)"]

    year = st.session_state.global_year
    grid_filter = st.session_state.global_grid

    # ------------------- Metric Calculations (needed for dynamic banner) -------------------
    gen_nat = gen[gen["Grid"].isin(GRIDS)]
    gen_yr = gen_nat[gen_nat["Year"] == year]
    gen_prev = gen_nat[gen_nat["Year"] == year - 1] if (year - 1) in gen_nat["Year"].values else None

    total_gen = gen_yr["Generation_MWh"].sum() / 1e6
    total_mwh = gen_yr["Generation_MWh"].sum()
    re_gen = gen_yr[gen_yr["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
    re_pct = re_gen / total_mwh * 100 if total_mwh > 0 else 0

    gen_trend = re_trend_pct = 0.0
    prev_re_pct = re_pct
    if gen_prev is not None and not gen_prev.empty:
        prev_gen = gen_prev["Generation_MWh"].sum() / 1e6
        gen_trend = (total_gen - prev_gen) / prev_gen * 100 if prev_gen > 0 else 0
        prev_re = gen_prev[gen_prev["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
        prev_re_pct = prev_re / gen_prev["Generation_MWh"].sum() * 100 if gen_prev["Generation_MWh"].sum() > 0 else 0
        re_trend_pct = re_pct - prev_re_pct

    sl_nat = sl[sl["Grid"] == "Philippines"]
    sl_yr_rows = sl_nat[sl_nat["Year"] == year]
    avg_sl = sl_yr_rows["SystemLoss_pct"].mean() if not sl_yr_rows.empty else 0.0
    sl_prev_val = sl_nat[sl_nat["Year"] == year - 1]["SystemLoss_pct"].mean() if (year - 1) in sl_nat["Year"].values else None
    sl_trend = avg_sl - sl_prev_val if sl_prev_val is not None else 0.0

    peak_mw = dem_trend = 0.0
    if not hourly.empty:
        dem_yr = hourly[hourly["Year"] == year]
        peak_mw = dem_yr["DailyPeak_MW"].max() if not dem_yr.empty else 0.0
        dem_prev_val = hourly[hourly["Year"] == year - 1]["DailyPeak_MW"].max() if (year - 1) in hourly["Year"].values else None
        dem_trend = (peak_mw - dem_prev_val) / dem_prev_val * 100 if dem_prev_val and dem_prev_val > 0 else 0.0

    re_gap = max(0.0, TARGET_RE_2030 - re_pct)
    risk_count = sum([avg_sl > TARGET_SYSTEM_LOSS, re_pct < TARGET_RE_2030 * 0.7, dem_trend > 5])

    _briefing_text = generate_briefing(avg_sl, re_pct, risk_count, re_gap, TARGET_SYSTEM_LOSS, TARGET_RE_2030)

    st.markdown(
        '<h1>PH GridWatch</h1>'
        '<div class="page-description">National Energy Command Center</div>'
        '<div class="executive-summary-banner">'
        '<div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">'
        '<div style="display: flex; align-items: center; gap: var(--space-8);">'
        '<span class="banner-tag">BRIEFING</span>'
        f'<span class="banner-text">{_briefing_text}</span>'
        '</div>'
        f'<span class="banner-refresh">Last Updated: {st.session_state.last_updated}</span>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Derived scores ────────────────────────────────────────────────────────
    # Operational Health: purely system efficiency (no policy targets mixed in)
    health_score = round(max(0.0, min(100.0,
        100.0 - avg_sl * 6.0 + min(0.0, gen_trend) * 1.0
    )), 1)
    # Energy Security: standard formula consistent with EnergySecurity page
    sec_score, _adq, _div, _eff = compute_energy_security_score(re_pct, dem_trend, avg_sl)

    # ── Standardised 4-level status vocabulary ───────────────────────────────
    gen_status    = "NOMINAL" if -2 < gen_trend < 2 else ("NOMINAL" if gen_trend >= 2 else "WATCH")
    dem_status    = ("CRITICAL" if dem_trend > 8 else
                     "ELEVATED" if dem_trend > 5 else
                     "WATCH"    if dem_trend > 3 else "NOMINAL")
    re_status     = ("NOMINAL"  if re_pct >= TARGET_RE_2030 * 0.95 else
                     "WATCH"    if re_gap < 10 else
                     "ELEVATED" if re_gap < 20 else "CRITICAL")
    loss_status   = ("NOMINAL"  if avg_sl <= TARGET_SYSTEM_LOSS else
                     "WATCH"    if avg_sl <= TARGET_SYSTEM_LOSS + 0.5 else
                     "ELEVATED" if avg_sl <= TARGET_SYSTEM_LOSS + 1.5 else "CRITICAL")
    health_status = ("NOMINAL"  if health_score >= 85 else
                     "WATCH"    if health_score >= 70 else
                     "ELEVATED" if health_score >= 55 else "CRITICAL")
    sec_status    = ("NOMINAL"  if sec_score >= 70 else
                     "WATCH"    if sec_score >= 55 else
                     "ELEVATED" if sec_score >= 40 else "CRITICAL")

    # National Energy Risk Index — no circular dependency between components
    _loss_risk = min(100.0, max(0.0, avg_sl - TARGET_SYSTEM_LOSS) / TARGET_SYSTEM_LOSS * 100)
    _re_risk   = re_gap / TARGET_RE_2030 * 100
    _dem_risk  = min(100.0, max(0.0, dem_trend - 2.0) / 10.0 * 100)
    _gen_risk  = min(100.0, max(0.0, -gen_trend) / 10.0 * 100)
    risk_score = round(max(0.0, min(100.0,
        _loss_risk * 0.35 + _re_risk * 0.30 + _dem_risk * 0.25 + _gen_risk * 0.10
    )), 1)

    prev_sl_safe  = sl_prev_val if sl_prev_val is not None else avg_sl
    prev_re_gap   = max(0.0, TARGET_RE_2030 - prev_re_pct)
    prev_risk_score = round(max(0.0, min(100.0,
        (min(100.0, max(0.0, prev_sl_safe - TARGET_SYSTEM_LOSS) / TARGET_SYSTEM_LOSS * 100)) * 0.35 +
        (prev_re_gap / TARGET_RE_2030 * 100) * 0.30 +
        _dem_risk * 0.25 + 0.0 * 0.10
    )), 1)
    risk_trend = risk_score - prev_risk_score

    if risk_score > 65:
        risk_status = "CRITICAL"
        commentary_risk = f"Elevated national risk — {risk_count} alert{'s' if risk_count != 1 else ''} active."
    elif risk_score >= 35:
        risk_status = "ELEVATED"
        commentary_risk = "Moderate risk — monitoring loss and RE targets."
    else:
        risk_status = "NOMINAL"
        commentary_risk = "National risk index within acceptable range."

    # Dynamic commentaries — generated from actual data
    commentary_gen    = gen_commentary(gen_trend)
    commentary_demand = demand_commentary(dem_trend)
    commentary_re     = (f"{re_gap:.1f}pp gap to 2030 target."
                         if re_gap > 0 else f"Ahead of 2030 target by {-re_gap:.1f}pp.")
    commentary_loss   = (f"Above DOE target by {avg_sl - TARGET_SYSTEM_LOSS:.2f}pp."
                         if avg_sl > TARGET_SYSTEM_LOSS else "Within DOE target.")
    commentary_health = health_commentary(health_score, avg_sl, TARGET_SYSTEM_LOSS)
    commentary_sec    = sec_commentary(sec_score)

    # ==================== ROW 1: KPI CARDS ====================
    cols = st.columns(7, gap="small")
    _ic = "#8E9FAF"
    kpis = [
        ("Total Generation", f"{total_gen:.1f}",   "TWh", f"vs {year-1}", gen_trend,              gen_status, commentary_gen,    factory(16, _ic)),
        ("Peak Demand",      f"{peak_mw:,.0f}",    "MW",  f"vs {year-1}", dem_trend,              dem_status, commentary_demand, zap(16, _ic)),
        ("Renewable Share",  f"{re_pct:.1f}",      "%",   f"vs {year-1}", re_trend_pct,           re_status, commentary_re,      leaf(16, _ic)),
        ("System Loss",      f"{avg_sl:.2f}",      "%",   f"vs {year-1}", -sl_trend,              loss_status, commentary_loss,  activity(16, _ic)),
        ("Grid Health",      f"{health_score:.0f}", "",   "vs baseline",  health_score - 85,      health_status, commentary_health, heart_pulse(16, _ic)),
        ("Energy Security",  f"{sec_score:.0f}",   "",    "vs baseline",  sec_score - 72,         sec_status, commentary_sec,    shield_check(16, _ic)),
        ("National Energy Risk", f"{risk_score:.0f}", "", "vs baseline",  risk_trend,             risk_status, commentary_risk,  alert_tri(16, _ic)),
    ]
    for i, (label, val, unit, ctx, trend, status, comment, icon) in enumerate(kpis):
        with cols[i]:
            st.markdown(kpi_card(label, val, unit, ctx, trend, status, comment, icon), unsafe_allow_html=True)

    # ==================== ROW 2: STATUS BAR ====================
    risk_color = "#EF4444" if risk_count >= 2 else ("#F59E0B" if risk_count == 1 else "#10B981")
    risk_label = "Critical" if risk_count >= 2 else ("Watch" if risk_count == 1 else "Nominal")
    sl_color   = "#EF4444" if avg_sl > TARGET_SYSTEM_LOSS else "#10B981"
    re_color   = "#10B981" if re_trend_pct >= 0 else "#EF4444"

    st.markdown(f"""
    <div class="briefing-strip">
      <div class="briefing-item"><span class="briefing-text">System Status</span><span class="briefing-value" style="color:{risk_color}">{risk_label} · {risk_count} risk{"s" if risk_count != 1 else ""}</span></div>
      <div class="briefing-item"><span class="briefing-text">Transmission Loss</span><span class="briefing-value" style="color:{sl_color}">{avg_sl:.2f}% · target {TARGET_SYSTEM_LOSS}%</span></div>
      <div class="briefing-item"><span class="briefing-text">RE Progress</span><span class="briefing-value" style="color:{re_color}">{re_pct:.1f}% · {re_gap:.1f}pp to 2030 target</span></div>
      <div class="briefing-item"><span class="briefing-text">Operational Health / Security</span><span class="briefing-value">{health_score:.0f} / {sec_score:.0f}</span></div>
    </div>
    """, unsafe_allow_html=True)

    # ==================== ROW 3: NATIONAL ENERGY INTELLIGENCE ====================
    st.markdown('<div class="section-header">National Energy Intelligence</div>', unsafe_allow_html=True)

    # Prepare delivery data for map
    df_agg = pd.DataFrame()
    value_col = None
    if delivery is not None and not delivery.empty:
        df_del = delivery[delivery["Year"] == year].copy() if "Year" in delivery.columns else delivery.copy()
        region_col = "Region" if "Region" in df_del.columns else "region_name"
        value_col  = "Delivery_MWh" if "Delivery_MWh" in df_del.columns else ("delivery_mwh" if "delivery_mwh" in df_del.columns else None)
        if value_col:
            df_agg = df_del.groupby(region_col)[value_col].sum().reset_index()
            df_agg["region_key"] = df_agg[region_col].apply(normalise_region_name)
            df_agg = df_agg[~df_agg["region_key"].isin(EXCLUDE_REGIONS) & df_agg["region_key"].notna()]

    geojson, geojson_mapping, _ = load_geojson_and_mapping("ph_regions.json")

    def map_layer_style(layer_name, values):
        if layer_name == "System Loss (%)":
            scale = [[0.0, "#10B981"], [0.5, "#F59E0B"], [1.0, "#EF4444"]]
        elif layer_name == "RE Share (%)":
            scale = [[0.0, "#EF4444"], [0.45, "#F59E0B"], [1.0, "#10B981"]]
        else:
            scale = [[0.0, "#0B3B60"], [0.35, "#1E88E5"], [0.7, "#43A047"], [1.0, "#FDD835"]]

        clean = pd.to_numeric(values, errors="coerce").dropna()
        positive = clean[clean > 0]
        if not positive.empty and positive.max() > positive.min():
            return scale, (float(positive.min()), float(positive.max()))
        if not clean.empty and clean.max() > clean.min():
            return scale, (float(clean.min()), float(clean.max()))
        return scale, None

    def build_map_layer(layer_name):
        if layer_name == "Delivery (MWh)" and not df_agg.empty and value_col:
            return (df_agg[["region_key", value_col]]
                    .rename(columns={value_col: "map_value"})
                    .assign(map_label="Delivery MWh"))
        rows = []
        for grid_name, regions in GRID_TO_REGIONS.items():
            if layer_name == "Generation (MWh)":
                map_value = gen[(gen["Year"] == year) & (gen["Grid"] == grid_name)]["Generation_MWh"].sum()
                map_label = "Generation MWh"
            elif layer_name == "Demand (MW)":
                map_value = (hourly[(hourly["Year"] == year) & (hourly["Grid"] == grid_name)]["DailyPeak_MW"].max()
                             if not hourly.empty else 0)
                map_label = "Peak Demand MW"
            elif layer_name == "System Loss (%)":
                row = sl[(sl["Year"] == year) & (sl["Month"] == "Total") & (sl["Grid"] == grid_name)]
                map_value = row["SystemLoss_pct"].mean() if not row.empty else 0
                map_label = "System Loss %"
            elif layer_name == "RE Share (%)":
                g_yr = gen[(gen["Year"] == year) & (gen["Grid"] == grid_name)]
                tot  = g_yr["Generation_MWh"].sum()
                ren  = g_yr[g_yr["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
                map_value = ren / tot * 100 if tot > 0 else 0
                map_label = "RE Share %"
            else:
                map_value, map_label = 0, layer_name
            map_value = 0 if pd.isna(map_value) else float(map_value)
            for region_key in regions:
                rows.append({"region_key": region_key, "map_value": map_value, "map_label": map_label})
        return pd.DataFrame(rows)

    import streamlit.components.v1 as _cv1

    # Column ratio: Map 60.0%, Panel 40.0%
    map_col, panel_col = st.columns([2.4, 1.6], gap="small")

    with map_col:
        # ── Map header ──
        st.markdown('<div class="map-header map-column-marker"><span class="map-title">Philippine Energy Intelligence Map</span></div>', unsafe_allow_html=True)

        # ── Layer tab bar (iframe) — clicks Plotly.restyle in parent ──
        _tab_items = "".join(
            f'<div class="tab{"  active" if i == 0 else ""}" onclick="pick({i})">{l}</div>'
            for i, l in enumerate(layers)
        )
        _cv1.html(f"""
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:transparent;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;overflow:hidden;}}
.tabs{{display:flex;gap:0;border-bottom:1px solid rgba(255,255,255,0.08);}}
.tab{{flex:1;text-align:center;padding:8px 4px 10px;font-size:11.5px;font-weight:400;
  color:rgba(140,160,185,0.55);cursor:pointer;border-bottom:2px solid transparent;
  margin-bottom:-1px;transition:color .15s,border-color .15s;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;user-select:none;}}
.tab:hover{{color:rgba(190,210,235,0.85);border-bottom-color:rgba(0,102,255,0.3);}}
.tab.active{{color:#fff;font-weight:600;border-bottom:2px solid #0066FF;}}
</style>
<div class="tabs">{_tab_items}</div>
<script>
var _active = 0;
var _n = {len(layers)};
function pick(idx){{
  if(idx === _active) return;
  var tabs = document.querySelectorAll('.tab');
  tabs[_active].classList.remove('active');
  tabs[idx].classList.add('active');
  _active = idx;
  try{{
    var gd = window.parent.document.querySelector('.js-plotly-plot');
    if(!gd) return;
    var vis = Array(_n).fill(false);
    vis[idx] = true;
    window.parent.Plotly.restyle(gd, {{visible: vis}});
  }}catch(e){{console.error('restyle error',e);}}
}}
</script>
""", height=42, scrolling=False)

        st.markdown('<div class="map-col-fill"></div>', unsafe_allow_html=True)
        if geojson is not None:
            # Determine geo filter
            if grid_filter != "All Grids" and grid_filter in GRID_TO_REGIONS:
                allowed = GRID_TO_REGIONS[grid_filter]
                geojson_use = {
                    "type": "FeatureCollection",
                    "features": [f for f in geojson["features"] if f["properties"]["name"] in allowed]
                }
            else:
                allowed = None
                geojson_use = geojson

            if geojson_use["features"]:
                geojson_with_key = geojson_use.copy()
                for feat in geojson_with_key["features"]:
                    feat["properties"]["match_key"] = feat["properties"]["name"]

                all_keys = pd.DataFrame({"region_key": list(geojson_mapping.keys())})
                if allowed:
                    all_keys = all_keys[all_keys["region_key"].isin(allowed)]

                if grid_filter == "Luzon":
                    map_zoom, map_center = 5.0, {"lat": 16.5, "lon": 121.0}
                elif grid_filter == "Visayas":
                    map_zoom, map_center = 6.0, {"lat": 10.8, "lon": 124.2}
                elif grid_filter == "Mindanao":
                    map_zoom, map_center = 5.5, {"lat": 7.8, "lon": 125.0}
                else:
                    map_zoom, map_center = 4.8, {"lat": 12.2, "lon": 122.5}

                import plotly.graph_objects as go
                traces = []
                for i, layer_name in enumerate(layers):
                    df_metric = build_map_layer(layer_name)
                    df_region = (all_keys
                                 .merge(df_metric, on="region_key", how="left")
                                 .assign(map_value=lambda d: d["map_value"].fillna(0),
                                         map_label=lambda d: d["map_label"].fillna(layer_name)))
                    color_scale, color_range = map_layer_style(layer_name, df_region["map_value"])
                    zmin, zmax = (color_range if color_range else (None, None))

                    trace = go.Choroplethmapbox(
                        geojson=geojson_with_key,
                        locations=df_region["region_key"],
                        z=df_region["map_value"],
                        colorscale=color_scale,
                        zmin=zmin,
                        zmax=zmax,
                        visible=(i == 0),
                        name=layer_name,
                        featureidkey="properties.match_key",
                        marker_opacity=0.9,
                        marker_line_width=0.5,
                        marker_line_color="rgba(255,255,255,0.15)",
                        colorbar=dict(
                            title=dict(text=layer_name, font=dict(color="#F8FAFC", size=11)),
                            tickfont=dict(color="#8E9FAF", size=10),
                            thickness=12,
                            len=0.62,
                            x=1.0,
                            bgcolor="rgba(7,13,25,0.92)",
                            outlinecolor="rgba(30,43,71,0.7)",
                            outlinewidth=1,
                        ),
                        hovertemplate="<b>%{location}</b><br>" + layer_name + ": %{z:.2f}<extra></extra>",
                    )
                    traces.append(trace)

                fig_map = go.Figure(data=traces)
                fig_map.update_layout(
                    mapbox=dict(
                        style="carto-darkmatter",
                        zoom=map_zoom,
                        center=map_center,
                    ),
                    margin=dict(l=8, r=8, t=8, b=8),
                    height=600,
                    paper_bgcolor="rgba(7,10,20,0.6)",
                    dragmode=False,
                )
                st.plotly_chart(fig_map, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

    with panel_col:
        lz_yr = gen[(gen["Grid"] == "Luzon") & (gen["Year"] == year)]
        lz_tot = lz_yr["Generation_MWh"].sum()
        lz_coal = lz_yr[lz_yr["PlantType"] == "Coal"]["Generation_MWh"].sum()
        lz_coal_pct = lz_coal / lz_tot * 100 if lz_tot > 0 else 0

        alert_status_class = "danger" if risk_count >= 2 else ("warning" if risk_count == 1 else "success")
        alert_status_text = "ACTIVE" if risk_count >= 2 else ("WATCH" if risk_count == 1 else "LOW")
        loss_risk_class = "high" if avg_sl > TARGET_SYSTEM_LOSS else "low"
        reserve_risk_class = "high" if dem_trend > 5 else ("medium" if dem_trend >= 2 else "low")
        re_gap_class = "high" if re_pct < TARGET_RE_2030 * 0.7 else ("medium" if re_gap > 0 else "low")
        coal_risk_class = "medium" if lz_coal_pct >= 50 else "low"
        demand_trend_class = "positive" if dem_trend <= 5 else "negative"
        loss_trend_class = "positive" if sl_trend <= 0 else "negative"
        generation_trend_class = "positive" if gen_trend >= 0 else "negative"

        # Fuel Mix Intelligence Calculations
        fuel_mix = gen_yr.groupby("PlantType")["Generation_MWh"].sum()
        fuel_total = fuel_mix.sum()
        fuel_categories = {
            "Coal": ["Coal"],
            "Natural Gas": ["Combined Cycle / Natural Gas", "Gas Turbine", "Natural Gas"],
            "Oil": ["Diesel", "Thermal"],
            "Hydro": ["Hydro"],
            "Solar": ["Renewable (Solar)"],
            "Wind": ["Renewable (Wind)"],
            "Geothermal": ["Geothermal"],
            "Biomass": ["Renewable (Biomass)", "Bio-Gas"]
        }
        fuel_shares = {}
        for cat, plant_types in fuel_categories.items():
            cat_sum = sum(fuel_mix.get(pt, 0.0) for pt in plant_types)
            fuel_shares[cat] = (cat_sum / fuel_total * 100) if fuel_total > 0 else 0.0

        fuel_mix_items_html = ""
        for fuel, share in fuel_shares.items():
            fuel_mix_items_html += f'<div class="fuel-mix-item"><span class="fuel-mix-label">{fuel}</span><span class="fuel-mix-value">{share:.1f}%</span></div>'

        # Energy Transition Tracker Calculations
        gap_2030 = re_pct - TARGET_RE_2030
        gap_2040 = re_pct - TARGET_RE_2040
        gap_2030_class = "positive" if gap_2030 >= 0 else "negative"
        gap_2040_class = "positive" if gap_2040 >= 0 else "negative"

        transition_html = f"""
<div class="transition-grid">
    <div class="transition-item">
        <span class="transition-label">Current RE</span>
        <span class="transition-value">{re_pct:.1f}%</span>
    </div>
    <div class="transition-item">
        <span class="transition-label">2030 Target</span>
        <span class="transition-value">35.0%</span>
    </div>
    <div class="transition-item">
        <span class="transition-label">2040 Target</span>
        <span class="transition-value">50.0%</span>
    </div>
    <div class="transition-item">
        <span class="transition-label">Gap to 2030</span>
        <span class="transition-value {gap_2030_class}">{gap_2030:+.1f}%</span>
    </div>
</div>
"""

        # Render panel via markdown with indentation stripped to avoid markdown parsing raw HTML as code blocks
        _ti = "#8E9FAF"
        sys_status_html = f"""
<div class="intel-panel">
    <div class="intel-section">
        <div class="intel-section-title">{heart_pulse(14, _ti)} System Status</div>
        <div class="readiness-grid">
            <div class="readiness-card"><div class="readiness-label">Operational Health</div><div class="readiness-score">{health_score:.0f}</div><div class="readiness-status status-{"success" if health_score>=85 else "warning"}">{"NOMINAL" if health_score>=85 else "WATCH"}</div></div>
            <div class="readiness-card"><div class="readiness-label">Energy Security</div><div class="readiness-score">{sec_score:.0f}</div><div class="readiness-status status-{"success" if sec_score>=70 else "warning" if sec_score>=50 else "danger"}">{"NOMINAL" if sec_score>=70 else "WATCH" if sec_score>=50 else "CRITICAL"}</div></div>
            <div class="readiness-card"><div class="readiness-label">Critical Alerts</div><div class="readiness-score">{risk_count}</div><div class="readiness-status status-{alert_status_class}">{alert_status_text}</div></div>
        </div>
    </div>
    <div class="intel-section">
        <div class="intel-section-title">{alert_tri(14, _ti)} Live Risk Assessment</div>
        <div class="hotspot-item"><span class="hotspot-name">High Transmission Loss</span><span class="hotspot-status {loss_risk_class}">{avg_sl:.2f}% vs {TARGET_SYSTEM_LOSS}%</span></div>
        <div class="hotspot-item"><span class="hotspot-name">Reserve Margin Risk</span><span class="hotspot-status {reserve_risk_class}">{dem_trend:+.1f}% demand growth</span></div>
        <div class="hotspot-item"><span class="hotspot-name">RE Target Gap</span><span class="hotspot-status {re_gap_class}">{re_gap:.1f}pp to 2030</span></div>
        <div class="hotspot-item"><span class="hotspot-name">Coal Dependency</span><span class="hotspot-status {coal_risk_class}">{lz_coal_pct:.0f}% share</span></div>
    </div>
    <div class="intel-section">
        <div class="intel-section-title">{factory(14, _ti)} Fuel Mix Intelligence</div>
        <div class="fuel-mix-grid">
            {fuel_mix_items_html}
        </div>
    </div>
    <div class="intel-section">
        <div class="intel-section-title">Energy Transition Tracker</div>
        {transition_html}
    </div>
    <div class="intel-section">
        <div class="intel-section-title">Causal Chain</div>
        <div style="font-size:10px;color:var(--text-secondary);line-height:1.7">
            <div>Loss {avg_sl:.2f}% → Est. ₱{(total_mwh*(avg_sl/100)*5.5/1e9):.1f}B cost → effective delivered energy reduced</div>
            <div>RE gap {re_gap:.1f}pp → need +{(re_gap/max(1,2030-year)):.1f}pp/yr → {("auction acceleration needed" if re_gap>5 else "current pace sufficient")}</div>
            <div>Demand {dem_trend:+.1f}% → {"capacity additions urgent" if dem_trend>5 else "capacity additions planned" if dem_trend>2 else "demand stable"} → {"storage firming critical" if re_pct>25 else "coal displacement priority"}</div>
        </div>
    </div>
</div>
"""
        sys_status_html_clean = "\n".join([line.strip() for line in sys_status_html.split("\n")])
        st.markdown(sys_status_html_clean, unsafe_allow_html=True)

    # ==================== ROW 4: NATIONAL ENERGY TRENDS ====================
    st.markdown('<div class="section-header">National Energy Trends</div>', unsafe_allow_html=True)
    cols_trends = st.columns(2, gap="small")
    years_range = sorted(gen["Year"].unique())[-10:]

    with cols_trends[0]:
        st.caption("Historical peak demand & generation with 3-year linear forecast (95% CI shaded).")
        trend_data = []
        for y in years_range:
            d = (hourly[hourly["Year"] == y]["DailyPeak_MW"].max()
                 if not hourly.empty and y in hourly["Year"].values else 0)
            g = gen[gen["Year"] == y]["Generation_MWh"].sum() / 1e6
            trend_data.append({"Year": y, "Demand": d, "Generation": g})
        df_trend = pd.DataFrame(trend_data)
        if not df_trend.empty:
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=df_trend["Year"], y=df_trend["Demand"],
                                           name="Peak Demand (MW)", mode="lines+markers",
                                           line=dict(color="#3B82F6", width=2)))
            fig_trend.add_trace(go.Scatter(x=df_trend["Year"], y=df_trend["Generation"] * 1000,
                                           name="Generation (GWh)", mode="lines+markers",
                                           line=dict(color="#10B981", width=2), yaxis="y2"))
            # Demand forecast with confidence bands
            fy, fp, flo, fhi = forecast_annual_peak(df_trend, "Year", "Demand", years_ahead=3)
            if len(fy) > 0:
                # Connect last historical point to forecast for visual continuity
                last_yr = df_trend["Year"].iloc[-1]
                last_dem = df_trend["Demand"].iloc[-1]
                fy_ext = np.concatenate([[last_yr], fy])
                fp_ext = np.concatenate([[last_dem], fp])
                flo_ext = np.concatenate([[last_dem], flo])
                fhi_ext = np.concatenate([[last_dem], fhi])
                fig_trend.add_trace(go.Scatter(
                    x=list(fy_ext) + list(fy_ext[::-1]),
                    y=list(fhi_ext) + list(flo_ext[::-1]),
                    fill="toself", fillcolor="rgba(59,130,246,0.12)",
                    line=dict(color="rgba(0,0,0,0)"), name="Demand 95% CI", showlegend=False))
                fig_trend.add_trace(go.Scatter(
                    x=fy_ext, y=fp_ext, name="Demand Forecast",
                    mode="lines", line=dict(color="#3B82F6", width=2, dash="dot")))
            fig_trend.update_layout(
                height=240, template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=6, r=6, t=8, b=8),
                xaxis=dict(tickfont=dict(size=13)),
                yaxis=dict(title="Demand (MW)", title_font=dict(size=14), tickfont=dict(size=12), color="#3B82F6"),
                yaxis2=dict(title="Generation (GWh)", title_font=dict(size=14), tickfont=dict(size=12),
                            overlaying="y", side="right", color="#10B981"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=13), x=0),
                hovermode="x unified",
            )
            st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})

    with cols_trends[1]:
        st.caption("RE share trend with linear trajectory projected to 2030 target line.")
        re_data = []
        for y in sorted(gen["Year"].unique()):
            g_yr = gen[gen["Year"] == y]
            tot  = g_yr["Generation_MWh"].sum()
            ren  = g_yr[g_yr["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
            re_data.append({"Year": y, "RE_Share": ren / tot * 100 if tot > 0 else 0})
        df_re = pd.DataFrame(re_data)
        if not df_re.empty:
            # Project trend to 2030
            proj_2030, slope_yr, proj_lo, proj_hi = forecast_re_trajectory(df_re, "Year", "RE_Share", 2030)
            fig_re = go.Figure()
            fig_re.add_trace(go.Scatter(x=df_re["Year"], y=df_re["RE_Share"],
                                        name="RE Share (%)", mode="lines+markers",
                                        line=dict(color="#10B981", width=2),
                                        marker=dict(size=5, color="#10B981")))
            if proj_2030 is not None:
                last_yr_re = df_re["Year"].iloc[-1]
                last_re = df_re["RE_Share"].iloc[-1]
                proj_years = list(range(int(last_yr_re), 2031))
                proj_vals = [last_re + slope_yr * (y - last_yr_re) for y in proj_years]
                # CI bounds (linear extrapolation of margin at 2030)
                margin_2030 = proj_2030 - proj_lo
                proj_hi_vals = [v + margin_2030 * (y - last_yr_re) / (2030 - last_yr_re + 1e-9) for v, y in zip(proj_vals, proj_years)]
                proj_lo_vals = [v - margin_2030 * (y - last_yr_re) / (2030 - last_yr_re + 1e-9) for v, y in zip(proj_vals, proj_years)]
                fig_re.add_trace(go.Scatter(
                    x=proj_years + proj_years[::-1],
                    y=proj_hi_vals + proj_lo_vals[::-1],
                    fill="toself", fillcolor="rgba(16,185,129,0.10)",
                    line=dict(color="rgba(0,0,0,0)"), name="Trajectory 95% CI", showlegend=False))
                fig_re.add_trace(go.Scatter(
                    x=proj_years, y=proj_vals, name="Trajectory Projection",
                    mode="lines", line=dict(color="#10B981", width=2, dash="dot")))
                # Verdict annotation
                verdict_color = "#2DC653" if proj_2030 >= TARGET_RE_2030 else "#EF4444"
                verdict_text = (f"On track: {proj_2030:.1f}% by 2030"
                                if proj_2030 >= TARGET_RE_2030
                                else f"Miss: {proj_2030:.1f}% by 2030 ({proj_2030 - TARGET_RE_2030:.1f}pp short)")
                fig_re.add_annotation(x=2030, y=proj_2030, text=verdict_text,
                                      showarrow=True, arrowhead=2, arrowcolor=verdict_color,
                                      font=dict(color=verdict_color, size=11),
                                      bgcolor="rgba(7,13,25,0.85)", bordercolor=verdict_color, borderwidth=1,
                                      ax=-80, ay=-30)
            fig_re.add_hline(y=TARGET_RE_2030, line_dash="dash", line_width=2, line_color="rgba(245,158,11,0.8)",
                             annotation_text=f"2030 Target ({TARGET_RE_2030}%)", annotation_position="right",
                             annotation_font_size=13)
            fig_re.update_layout(
                xaxis_title="Year", yaxis_title="RE Share (%)",
                height=240, margin=dict(l=6, r=6, t=8, b=8),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(tickfont=dict(size=13), title_font=dict(size=14)),
                yaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=12), x=0),
                hovermode="x unified",
            )
            st.plotly_chart(fig_re, use_container_width=True, config={"displayModeBar": False})

    # ==================== ROW 5: SYSTEM LOSS TREND ====================
    st.markdown('<div class="section-header">System Loss Trend</div>', unsafe_allow_html=True)
    sl_annual = sl[(sl["Month"] == "Total") & (sl["Grid"].isin(GRIDS+["Philippines"]))]
    if not sl_annual.empty:
        fig_sl = px.line(sl_annual, x="Year", y="SystemLoss_pct", color="Grid",
                         color_discrete_map={"Luzon":"#00C2FF","Visayas":"#F4A261","Mindanao":"#2DC653","Philippines":"#C77DFF"},
                         markers=True, template="plotly_dark", labels={"SystemLoss_pct": "Loss (%)"})
        fig_sl.add_hline(y=TARGET_SYSTEM_LOSS, line_dash="dash", line_width=2, line_color="green",
                         annotation_text=f"DOE target {TARGET_SYSTEM_LOSS}%", annotation_position="bottom right",
                         annotation_font_size=14)
        fig_sl.update_layout(height=240, margin=dict(l=6, r=6, t=8, b=8),
                             paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                             xaxis=dict(tickfont=dict(size=13), title_font=dict(size=14)),
                             yaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
                             legend=dict(font=dict(size=13)))
        st.plotly_chart(fig_sl, use_container_width=True, config={"displayModeBar": False})

    # ==================== ROW 6: REGIONAL PERFORMANCE CARDS ====================
    st.markdown('<div class="section-header">Regional Performance</div>', unsafe_allow_html=True)
    region_cols = st.columns(3, gap="small")
    for i, grid_name in enumerate(GRIDS):
        g_yr = gen[(gen["Grid"] == grid_name) & (gen["Year"] == year)]
        g_gen_twh = g_yr["Generation_MWh"].sum() / 1e6
        g_tot = g_yr["Generation_MWh"].sum()
        g_re = g_yr[g_yr["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
        g_re_pct = g_re / g_tot * 100 if g_tot > 0 else 0
        g_peak = 0.0
        if not hourly.empty and grid_name in hourly["Grid"].values:
            g_peak_row = hourly[(hourly["Grid"] == grid_name) & (hourly["Year"] == year)]["DailyPeak_MW"]
            g_peak = g_peak_row.max() if not g_peak_row.empty else 0.0
        g_sl_row = sl[(sl["Grid"] == grid_name) & (sl["Year"] == year) & (sl["Month"] == "Total")]
        g_sl = g_sl_row["SystemLoss_pct"].mean() if not g_sl_row.empty else 0.0
        g_health = round(max(0.0, min(100.0, 100.0 - g_sl * 6.0)), 0)
        if g_sl > TARGET_SYSTEM_LOSS + 0.5:
            g_status, g_status_class = "CRITICAL", "danger"
        elif g_sl > TARGET_SYSTEM_LOSS or g_re_pct < TARGET_RE_2030 * 0.5:
            g_status, g_status_class = "WATCH", "warning"
        else:
            g_status, g_status_class = "NOMINAL", "success"
        grid_class = grid_name.lower()
        with region_cols[i]:
            st.markdown(f"""
            <div class="region-card {grid_class}">
                <div class="region-card-header">
                    <span class="region-card-name">{grid_name} Grid</span>
                    <span class="status-badge status-{g_status_class}">{g_status}</span>
                </div>
                <div class="region-card-grid">
                    <div class="region-card-metric primary">
                        <div class="metric-label">Generation</div>
                        <div class="metric-val-row"><span class="metric-value primary">{g_gen_twh:.2f}</span><span class="metric-unit">TWh</span></div>
                    </div>
                    <div class="region-card-metric secondary">
                        <div class="metric-label">Peak Demand</div>
                        <div class="metric-val-row"><span class="metric-value secondary">{g_peak:,.0f}</span><span class="metric-unit">MW</span></div>
                    </div>
                    <div class="region-card-metric tertiary">
                        <div class="metric-label">RE Share</div>
                        <div class="metric-val-row"><span class="metric-value tertiary">{g_re_pct:.1f}</span><span class="metric-unit">%</span></div>
                    </div>
                    <div class="region-card-metric tertiary">
                        <div class="metric-label">System Loss</div>
                        <div class="metric-val-row"><span class="metric-value tertiary">{g_sl:.2f}</span><span class="metric-unit">%</span></div>
                    </div>
                </div>
                <div class="region-card-footer">
                    <span class="footer-label">Health Score</span>
                    <span class="risk-badge risk-{"critical" if g_health<50 else "medium" if g_health<70 else "low"}">{g_health:.0f}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ==================== ROW 7: POLICY INTELLIGENCE ====================
    st.markdown('<div class="section-header">Policy Intelligence</div>', unsafe_allow_html=True)
    cols_policy = st.columns(3, gap="small")
    _coal_threshold = 50.0
    _coal_impact = (f"Luzon coal {lz_coal_pct:.0f}% — above {_coal_threshold:.0f}% concentration threshold"
                    if lz_coal_pct > _coal_threshold
                    else f"Luzon coal {lz_coal_pct:.0f}% — below {_coal_threshold:.0f}% concern threshold")
    _coal_action = ("➔ Accelerate retirement of ageing coal plants"
                    if lz_coal_pct > _coal_threshold
                    else "➔ Maintain RE pressure to displace remaining coal")
    _loss_impact = (f"Loss {avg_sl:.2f}% is {avg_sl - TARGET_SYSTEM_LOSS:.2f}pp above the {TARGET_SYSTEM_LOSS}% DOE target"
                    if avg_sl > TARGET_SYSTEM_LOSS
                    else f"Loss {avg_sl:.2f}% is within the {TARGET_SYSTEM_LOSS}% DOE target")
    _loss_action = ("➔ Mandate NGCP transmission audit" if avg_sl > TARGET_SYSTEM_LOSS
                    else "➔ Sustain grid maintenance programme")
    _yrs_left = max(1, 2030 - year)
    _re_rate_needed = re_gap / _yrs_left if _yrs_left > 0 else 0
    _re_action = (f"➔ Need +{_re_rate_needed:.1f}pp RE/year to meet 2030 target"
                  if re_gap > 0 else "➔ Sustain RE deployment momentum")

    with cols_policy[0]:
        st.markdown(f"""
        <div class="policy-card critical">
            <div class="policy-card-title">Critical Risks</div>
            <div class="policy-item"><div class="policy-item-title">Coal Dependency</div><div class="policy-item-impact">{_coal_impact}</div><div class="policy-item-action">{_coal_action}</div></div>
            <div class="policy-item"><div class="policy-item-title">Transmission Losses</div><div class="policy-item-impact">{_loss_impact}</div><div class="policy-item-action">{_loss_action}</div></div>
        </div>
        """, unsafe_allow_html=True)
    with cols_policy[1]:
        st.markdown(f"""
        <div class="policy-card emerging">
            <div class="policy-card-title">Emerging Risks</div>
            <div class="policy-item"><div class="policy-item-title">Demand Growth</div><div class="policy-item-impact">Peak demand {dem_trend:+.1f}% YoY — {"capacity adequacy risk elevated" if dem_trend > 5 else "within manageable range"}</div><div class="policy-item-action">➔ {"Fast-track capacity projects" if dem_trend > 5 else "Continue demand monitoring"}</div></div>
            <div class="policy-item"><div class="policy-item-title">RE Integration</div><div class="policy-item-impact">Total RE at {re_pct:.1f}% — grid balancing challenge as VRE share grows</div><div class="policy-item-action">➔ Deploy grid-scale battery storage</div></div>
        </div>
        """, unsafe_allow_html=True)
    with cols_policy[2]:
        st.markdown(f"""
        <div class="policy-card opportunity">
            <div class="policy-card-title">Strategic Opportunities</div>
            <div class="policy-item"><div class="policy-item-title">2030 RE Target</div><div class="policy-item-impact">{re_gap:.1f}pp gap to {TARGET_RE_2030}% — {_re_rate_needed:.1f}pp/year needed</div><div class="policy-item-action">{_re_action}</div></div>
            <div class="policy-item"><div class="policy-item-title">Demand Response</div><div class="policy-item-impact">Peak shaving can defer ₱{(peak_mw*0.05*8760*8/1e9):.1f}B in new capacity spend</div><div class="policy-item-action">➔ Launch DSM pilot programme</div></div>
        </div>
        """, unsafe_allow_html=True)

    # ==================== ROW 8: EXPORT SECTION ====================
    st.markdown('<div class="section-header export-header">Export & Downloads</div>', unsafe_allow_html=True)
    export_rows = [
        {"Metric": "Total Generation (TWh)",     "Value": round(total_gen, 2),    "Year": year},
        {"Metric": "Peak Demand (MW)",           "Value": round(peak_mw, 0),      "Year": year},
        {"Metric": "Renewable Share (%)",        "Value": round(re_pct, 2),       "Year": year},
        {"Metric": "System Loss (%)",            "Value": round(avg_sl, 2),       "Year": year},
        {"Metric": "Operational Health Score",   "Value": health_score,           "Year": year},
        {"Metric": "Energy Security Score",      "Value": sec_score,              "Year": year},
        {"Metric": "National Energy Risk Index", "Value": risk_score,             "Year": year},
        {"Metric": "Luzon Coal Share (%)",       "Value": round(lz_coal_pct, 1), "Year": year},
        {"Metric": "RE Gap to 2030 (pp)",        "Value": round(re_gap, 1),      "Year": year},
    ]
    export_csv = pd.DataFrame(export_rows).to_csv(index=False)

    # Phase 4: Executive Intelligence Briefing — rich text download
    _yrs_to_30 = max(1, 2030 - year)
    _re_rate_briefing = re_gap / _yrs_to_30 if _yrs_to_30 > 0 else 0
    _eco_loss_b = total_mwh * (avg_sl / 100) * 5.50 / 1e9
    _risk_lvl = "HIGH" if risk_score > 65 else ("MODERATE" if risk_score >= 35 else "LOW")
    _briefing_doc = f"""PH GRIDWATCH — NATIONAL ENERGY INTELLIGENCE BRIEF
Year: {year} | Generated by PH GridWatch v2
{'=' * 62}

I. EXECUTIVE BRIEFING
{'—' * 40}
{_briefing_text}

II. KEY PERFORMANCE INDICATORS
{'—' * 40}
  Total Generation       : {total_gen:.2f} TWh
  Peak Demand            : {peak_mw:,.0f} MW  ({dem_trend:+.1f}% YoY)
  Renewable Share        : {re_pct:.1f}%  (DOE 2030 target: {TARGET_RE_2030}%)
  System Loss            : {avg_sl:.2f}%  (DOE target: {TARGET_SYSTEM_LOSS}%)
  Operational Health     : {health_score:.0f} / 100  [{health_status}]
  Energy Security Score  : {sec_score:.0f} / 100  [{sec_status}]
  National Risk Index    : {risk_score:.0f} / 100  [{_risk_lvl} RISK]

III. RISK ASSESSMENT
{'—' * 40}
  Transmission Loss Excess : {max(0, avg_sl - TARGET_SYSTEM_LOSS):.2f}pp above DOE target
  Estimated Annual Cost    : ₱{_eco_loss_b:.1f}B (@₱5.50/kWh WESM proxy)
  RE Transition Gap        : {re_gap:.1f}pp to 2030 target
  Annual RE Rate Needed    : +{_re_rate_briefing:.1f}pp/year
  Luzon Coal Share         : {lz_coal_pct:.0f}%  (Concern threshold: 50%)
  Generation Growth        : {gen_trend:+.1f}% YoY
  Peak Demand Growth       : {dem_trend:+.1f}% YoY

IV. GRID-LEVEL SUMMARY
{'—' * 40}"""
    for _gn in ["Luzon", "Visayas", "Mindanao"]:
        _g_yr = gen[(gen["Grid"] == _gn) & (gen["Year"] == year)]
        _g_tot = _g_yr["Generation_MWh"].sum()
        _g_re = _g_yr[_g_yr["PlantType"].isin(RENEWABLE_TYPES)]["Generation_MWh"].sum()
        _g_re_pct = _g_re / _g_tot * 100 if _g_tot > 0 else 0
        _g_sl_row = sl[(sl["Grid"] == _gn) & (sl["Year"] == year) & (sl["Month"] == "Total")]
        _g_sl = _g_sl_row["SystemLoss_pct"].mean() if not _g_sl_row.empty else 0.0
        _briefing_doc += f"\n  {_gn:<10}: {_g_tot/1e6:.2f} TWh  |  RE {_g_re_pct:.1f}%  |  Loss {_g_sl:.2f}%"
    _briefing_doc += f"""

V. POLICY PRIORITIES
{'—' * 40}
  [{'URGENT' if avg_sl > TARGET_SYSTEM_LOSS else 'MONITOR'}] Transmission Loss Reduction — {avg_sl:.2f}% vs {TARGET_SYSTEM_LOSS}% target
  [{'URGENT' if re_gap > 10 else 'WATCH'}] RE Portfolio Expansion — {re_gap:.1f}pp gap, need +{_re_rate_briefing:.1f}pp/yr
  [{'URGENT' if lz_coal_pct > 50 else 'MONITOR'}] Coal Concentration — Luzon at {lz_coal_pct:.0f}%
  [{'URGENT' if dem_trend > 5 else 'PLAN'}] Capacity Adequacy — Peak demand {dem_trend:+.1f}% YoY

VI. DATA INTEGRITY NOTE
{'—' * 40}
  Sources : NGCP Grid Operations Reports, DOE Energy Statistics
  Scores  : Operational Health (system loss proxy), Energy Security
            (demand growth proxy — NOT a true reserve margin calculation).
            For policy decisions, supplement with NGCP official reserve
            margin and installed capacity data.

{'=' * 62}
This document was auto-generated by PH GridWatch National Energy
Intelligence Platform. All figures are indicative and subject to
official verification by DOE, NGCP, and ERC.
"""
    cols_export = st.columns(3, gap="small")
    with cols_export[0]:
        st.download_button("↓ Export Data", data=export_csv,
                           file_name=f"gridwatch_kpi_{year}.csv", mime="text/csv", use_container_width=True)
    with cols_export[1]:
        st.download_button("↓ Export Intelligence Brief", data=_briefing_doc,
                           file_name=f"gridwatch_brief_{year}.txt", mime="text/plain", use_container_width=True)
    with cols_export[2]:
        st.download_button("↓ Export Full Report", data=export_csv,
                           file_name=f"gridwatch_full_{year}.csv", mime="text/csv", use_container_width=True)

    # ==================== METHODOLOGY & TRANSPARENCY expander ====================
    with st.expander("About Methodology & Transparency", expanded=False):
        st.markdown("""
        <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.6;">
            <h4 style="color: var(--text-primary); margin-top: 0; margin-bottom: var(--space-8); font-size: 14px;">Methodology & Data Integrity</h4>
            <p style="margin-bottom: var(--space-8);">
                <b>Data Sources:</b> Gross generation, transmission system losses, and regional power deliveries are sourced directly from official reports published by the <b>National Grid Corporation of the Philippines (NGCP)</b> and the <b>Department of Energy (DOE)</b>.
            </p>
            <p style="margin-bottom: var(--space-8);">
                <b>Update Frequency:</b> Live system assessments are updated in accordance with the monthly and annual grid operations reports published by regional system operators.
            </p>
            <p style="margin-bottom: var(--space-8);">
                <b>KPI Definitions:</b>
                <ul style="margin-left: var(--space-16); margin-bottom: var(--space-8);">
                    <li><b>Operational Health Score:</b> Purely operational — measures system efficiency and generation stability. Formula: <code>100 − (System Loss × 6) + min(0, Gen Growth × 1.0)</code>. Does not include policy targets (RE gap) to avoid conflating operational performance with transition compliance.</li>
                    <li><b>Energy Security Score:</b> Composite of Supply-Demand Balance Proxy (40%), Fuel Diversity Index (40%), and Transmission Efficiency (20%). Uses <code>compute_energy_security_score()</code> consistently across all pages. Note: Supply-Demand Balance Proxy uses demand growth rate as a proxy — true reserve margin requires installed capacity data.</li>
                    <li><b>National Energy Risk Index:</b> Weighted composite (0–100) with no circular dependency: Transmission Risk (35%) + RE Transition Deficit (30%) + Demand Growth Stress (25%) + Generation Stability (10%). Each component measures a distinct risk dimension.</li>
                </ul>
            </p>
            <p style="margin-bottom: 0;">
                <b>Calculations:</b> Calculations are run against hourly load profiles and daily dispatch records. Data gaps are filled using linear interpolation of historical dispatch averages.
            </p>
        </div>
        """, unsafe_allow_html=True) 