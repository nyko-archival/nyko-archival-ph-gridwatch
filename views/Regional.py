# views/Regional.py

import json
import pandas as pd
import streamlit as st
import plotly.express as px
from shapely.geometry import shape
from shapely.ops import transform
import pyproj
from utils.icons import trophy, trending_up, arrow_down, scale
from components.ui import render_intel_summary

# -------------------------------------------------------------------
# Region name mapping: delivery data name -> GeoJSON 'name' property
# -------------------------------------------------------------------
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

# Regions to exclude from all charts (aggregates only)
EXCLUDE_REGIONS = {
    "TOTAL PHILIPPINES", "Total Philippines", "North Luzon", "South Luzon",
    "Non-Meralco", "Luzon", "Visayas", "Mindanao", "Negros Island Region",
    "Negros Island", None, ""
}

# Mapping from grid to list of region keys (as they appear after normalisation)
GRID_TO_REGIONS = {
    "Luzon": [
        "Ilocos", "Cagayan Valley", "Central Luzon", "Calabarzon", "Mimaropa",
        "Bicol", "National Capital Region", "Cordillera Administrative Region"
    ],
    "Visayas": [
        "Western Visayas", "Central Visayas", "Eastern Visayas"
    ],
    "Mindanao": [
        "Zamboanga Peninsula", "Northern Mindanao", "Davao", "Soccsksargen",
        "Caraga", "Autonomous Region in Muslim Mindanao"
    ]
}

# Colors for grid pie chart (consistent with other views)
COLORS = {"Luzon": "#00C2FF", "Visayas": "#F4A261", "Mindanao": "#2DC653"}

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
def extract_name_in_parentheses(name: str) -> str:
    if not isinstance(name, str):
        return ""
    start = name.find("(")
    end = name.find(")")
    if start != -1 and end != -1:
        return name[start+1:end].strip()
    return name.strip()

def normalise_region_name(name: str) -> str:
    if not isinstance(name, str):
        return None
    inner = extract_name_in_parentheses(name)
    if inner in REGION_MAPPING:
        return REGION_MAPPING[inner]
    if name in REGION_MAPPING:
        return REGION_MAPPING[name]
    norm = inner.title()
    if norm.endswith(" Region"):
        norm = norm[:-7]
    if "Bangsamoro" in norm:
        return "Autonomous Region in Muslim Mindanao"
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

def load_geojson_and_mapping(filepath="ph_regions.json"):
    try:
        with open(filepath, "r") as f:
            geojson = json.load(f)
        mapping = {}
        centroids = {}
        for feature in geojson["features"]:
            name = feature["properties"].get("name", "")
            if not name:
                continue
            region_key = name.strip()
            lat, lon = compute_centroid(feature["geometry"])
            if lat is not None and lon is not None:
                centroids[region_key] = (lat, lon)
            mapping[region_key] = feature
        return geojson, mapping, centroids
    except Exception as e:
        st.warning(f"Could not load GeoJSON: {e}. Falling back to scatter map.")
        return None, None, None

def prepare_region_aggregation(df, region_col="region_name", value_col="delivery_mwh"):
    if df.empty or region_col not in df.columns:
        return pd.DataFrame()
    df_agg = df.copy()
    df_agg["region_key"] = df_agg[region_col].apply(normalise_region_name)
    df_agg = df_agg[~df_agg["region_key"].isin(EXCLUDE_REGIONS)]
    df_agg = df_agg[df_agg["region_key"].notna()]
    df_agg = df_agg.groupby("region_key", as_index=False)[value_col].sum()
    return df_agg

def delivery_color_range(values):
    clean = pd.to_numeric(values, errors="coerce").dropna()
    positive = clean[clean > 0]
    if not positive.empty and positive.max() > positive.min():
        return (float(positive.min()), float(positive.max()))
    if not clean.empty and clean.max() > clean.min():
        return (float(clean.min()), float(clean.max()))
    return None

# -------------------------------------------------------------------
# Main view function
# -------------------------------------------------------------------
def show():
    st.markdown(
        '<h1>Regional Energy Delivery</h1>'
        '<div class="page-description">Energy delivered to end-consumers by region - geographic distribution and detailed breakdown</div>',
        unsafe_allow_html=True,
    )

    if "delivery_df" not in st.session_state or st.session_state.delivery_df.empty:
        st.error("No delivery data found. Please check data source.")
        return

    df_raw = st.session_state.delivery_df.copy()

    # Column detection
    if "Delivery_MWh" in df_raw.columns:
        df_raw.rename(columns={"Delivery_MWh": "delivery_mwh"}, inplace=True)
    elif "delivery_mwh" not in df_raw.columns:
        num_cols = df_raw.select_dtypes(include=["number"]).columns
        for col in num_cols:
            if col != "Year" and df_raw[col].max() > 1000:
                df_raw.rename(columns={col: "delivery_mwh"}, inplace=True)
                break
        if "delivery_mwh" not in df_raw.columns:
            st.error("Could not find a column with energy delivery values (expected 'Delivery_MWh').")
            return

    region_candidates = ["region_name", "Region", "region", "REGION", "Delivery Region"]
    region_col = None
    for col in region_candidates:
        if col in df_raw.columns:
            region_col = col
            break
    if region_col is None:
        string_cols = df_raw.select_dtypes(include=["object", "string"]).columns
        if len(string_cols) > 0:
            region_col = string_cols[0]
        else:
            st.error("No column suitable for region names found.")
            return
    df_raw.rename(columns={region_col: "region_name"}, inplace=True)

    # Global filters
    global_year = st.session_state.get("global_year", None)
    global_grid = st.session_state.get("global_grid", "All Grids")

    # Apply year filter
    if "Year" in df_raw.columns and global_year is not None:
        df_raw = df_raw[df_raw["Year"] == global_year]

    # Apply grid filter by mapping region names to grids
    if global_grid != "All Grids" and global_grid in GRID_TO_REGIONS:
        allowed_regions = GRID_TO_REGIONS[global_grid]
        # We need to filter based on normalised region names, so first normalise
        df_raw["temp_key"] = df_raw["region_name"].apply(normalise_region_name)
        df_raw = df_raw[df_raw["temp_key"].isin(allowed_regions)]
        df_raw = df_raw.drop(columns=["temp_key"])

    if df_raw.empty:
        st.info(f"No delivery data for Year={global_year}, Grid={global_grid}.")
        return

    # Date handling
    if "date" not in df_raw.columns:
        if "Year" in df_raw.columns and "Month" in df_raw.columns:
            df_raw["date"] = pd.to_datetime(df_raw["Year"].astype(str) + "-" + df_raw["Month"].astype(str) + "-01")
        else:
            df_raw["date"] = pd.NaT
    if "Year" not in df_raw.columns and "date" in df_raw.columns:
        df_raw["year"] = df_raw["date"].dt.year
    else:
        df_raw["year"] = df_raw["Year"]

    # Aggregate for map (excludes artificial aggregates)
    df_region_with_data = prepare_region_aggregation(df_raw, "region_name", "delivery_mwh")

    # Load GeoJSON and centroids
    geojson, geojson_mapping, centroids = load_geojson_and_mapping("ph_regions.json")
    use_choropleth = geojson is not None

    if use_choropleth:
        all_geojson_regions = pd.DataFrame({"region_key": list(geojson_mapping.keys())})
        df_region = all_geojson_regions.merge(df_region_with_data, on="region_key", how="left")
        df_region["delivery_mwh"] = df_region["delivery_mwh"].fillna(0)
    else:
        df_region = df_region_with_data

    # ----- Map (choropleth or fallback) -----
    if not df_region.empty:
        if use_choropleth:
            # For choropleth, we only show regions that belong to the selected grid (if not All Grids)
            if global_grid != "All Grids" and global_grid in GRID_TO_REGIONS:
                allowed = GRID_TO_REGIONS[global_grid]
                df_region = df_region[df_region["region_key"].isin(allowed)]
                # Also keep only those features in geojson to avoid errors
                geojson_filtered = {
                    "type": "FeatureCollection",
                    "features": [f for f in geojson["features"] if f["properties"]["name"] in allowed]
                }
                geojson_to_use = geojson_filtered
            else:
                geojson_to_use = geojson

            if not df_region.empty and geojson_to_use.get("features"):
                geojson_with_key = geojson_to_use.copy()
                for feature in geojson_with_key["features"]:
                    name = feature["properties"].get("name", "")
                    feature["properties"]["match_key"] = name.strip()

                fig = px.choropleth_mapbox(
                    df_region,
                    geojson=geojson_with_key,
                    locations="region_key",
                    color="delivery_mwh",
                    color_continuous_scale=[[0.0, "#0B3B60"], [0.35, "#1E88E5"], [0.7, "#43A047"], [1.0, "#FDD835"]],
                    range_color=delivery_color_range(df_region["delivery_mwh"]),
                    mapbox_style="carto-darkmatter",
                    zoom=5.0,
                    center={"lat": 12.5, "lon": 122.5},
                    opacity=0.8,
                    labels={"delivery_mwh": "Energy Delivery (MWh)"},
                    hover_data={"region_key": True, "delivery_mwh": ":.0f"},
                    featureidkey="properties.match_key"
                )
                fig.update_layout(
                    height=420,
                    margin={"r": 0, "t": 0, "l": 0, "b": 0},
                    coloraxis_colorbar=dict(
                        title=dict(text="MWh", font=dict(color="#F8FAFC", size=11)),
                        tickfont=dict(color="#8E9FAF", size=10),
                        thickness=14,
                        len=0.62,
                        x=0.98,
                        y=0.5,
                        bgcolor="rgba(7,13,25,0.92)",
                        outlinecolor="rgba(30,43,71,0.7)",
                        outlinewidth=1,
                    )
                )
                fig.update_traces(
                    hovertemplate="<b>%{location}</b><br>Delivery: %{z:,.0f} MWh<extra></extra>"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No matching regions for the selected grid in the GeoJSON.")
        else:
            # Fallback scatter map (only regions with data)
            if centroids and not df_region_with_data.empty:
                coord_df = pd.DataFrame([
                    {"region_key": k, "lat": v[0], "lon": v[1]} for k, v in centroids.items()
                ])
                df_scatter = df_region_with_data.merge(coord_df, on="region_key", how="inner")
                if not df_scatter.empty:
                    fig = px.scatter_mapbox(
                        df_scatter,
                        lat="lat", lon="lon",
                        size="delivery_mwh",
                        color="delivery_mwh",
                        color_continuous_scale=[[0.0, "#0B3B60"], [0.35, "#1E88E5"], [0.7, "#43A047"], [1.0, "#FDD835"]],
                        range_color=delivery_color_range(df_scatter["delivery_mwh"]),
                        size_max=25,
                        zoom=5.0,
                        center={"lat": 12.5, "lon": 122.5},
                        mapbox_style="carto-darkmatter",
                        hover_name="region_key",
                        labels={"delivery_mwh": "Energy Delivery (MWh)"},
                    )
                    fig.update_layout(
                        height=420,
                        margin={"r": 0, "t": 0, "l": 0, "b": 0},
                        coloraxis_colorbar=dict(
                            title=dict(text="MWh", font=dict(color="#F8FAFC", size=11)),
                            tickfont=dict(color="#8E9FAF", size=10),
                            thickness=14,
                            len=0.62,
                            bgcolor="rgba(7,13,25,0.92)",
                            outlinecolor="rgba(30,43,71,0.7)",
                            outlinewidth=1,
                        )
                    )
                    fig.update_traces(
                        hovertemplate="<b>%{hovertext}</b><br>Delivery: %{marker.size:,.0f} MWh<extra></extra>"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No scatter data to display.")
            else:
                st.error("Cannot display map – missing GeoJSON or centroids.")
    else:
        st.info("No regional data to display on the map.")

    # ----- KPIs (adapt to global_grid selection) -----
    st.markdown('<div class="section-header">Key Performance Indicators</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    def kpi(col, label, val, sub=""):
        col.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{val}</div>'
            f'<div class="kpi-sub">{sub}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if global_grid == "All Grids":
        total_ph = df_raw[df_raw["region_name"] == "TOTAL PHILIPPINES"]["delivery_mwh"].sum()
        luzon = df_raw[df_raw["region_name"] == "LUZON"]["delivery_mwh"].sum()
        visayas = df_raw[df_raw["region_name"] == "VISAYAS"]["delivery_mwh"].sum()
        mindanao = df_raw[df_raw["region_name"] == "MINDANAO"]["delivery_mwh"].sum()
        kpi(k1, "Philippines Total", f"{total_ph/1e6:.2f} TWh", f"{global_year}" if global_year else "")
        kpi(k2, "Luzon Delivery",    f"{luzon/1e6:.2f} TWh",  "")
        kpi(k3, "Visayas Delivery",  f"{visayas/1e6:.2f} TWh", "")
        kpi(k4, "Mindanao Delivery", f"{mindanao/1e6:.2f} TWh", "")
    else:
        total_grid = df_region_with_data["delivery_mwh"].sum()
        avg_grid = df_region_with_data["delivery_mwh"].mean() if not df_region_with_data.empty else 0
        max_grid = df_region_with_data["delivery_mwh"].max() if not df_region_with_data.empty else 0
        n_regions = len(df_region_with_data)
        kpi(k1, f"{global_grid} Total", f"{total_grid/1e6:.2f} TWh", f"{global_year}" if global_year else "")
        kpi(k2, "Average Delivery",    f"{avg_grid/1e3:.1f} GWh", "")
        kpi(k3, "Max Delivery",        f"{max_grid/1e3:.1f} GWh", "")
        kpi(k4, "Regions Active",      f"{n_regions}", "")

    # ── Regional Intelligence Panel ──────────────────────────────────
    if not df_region_with_data.empty and len(df_region_with_data) >= 2:
        sorted_asc  = df_region_with_data.sort_values("delivery_mwh", ascending=True)
        sorted_desc = df_region_with_data.sort_values("delivery_mwh", ascending=False)

        top_region   = sorted_desc.iloc[0]
        low_region   = sorted_asc.iloc[0]
        total_del    = df_region_with_data["delivery_mwh"].sum()
        top_share    = top_region["delivery_mwh"] / total_del * 100 if total_del > 0 else 0

        # Growth: requires multi-year data in session
        full_del = st.session_state.delivery_df.copy()
        if "Delivery_MWh" in full_del.columns:
            full_del.rename(columns={"Delivery_MWh": "delivery_mwh"}, inplace=True)
        growth_label = "N/A"
        growth_region = "N/A"
        if "Year" in full_del.columns and global_year is not None:
            prev_yr = global_year - 1
            prev_del = full_del[full_del["Year"] == prev_yr].copy()
            prev_del.rename(columns={c: "region_name" for c in prev_del.columns if c in ["Region","region","REGION","Delivery Region"]}, errors="ignore")
            if "region_name" not in prev_del.columns:
                rc = [c for c in prev_del.columns if c.lower() in ("region","region_name","delivery region")]
                if rc: prev_del.rename(columns={rc[0]: "region_name"}, inplace=True)
            if not prev_del.empty and "region_name" in prev_del.columns:
                prev_agg = prepare_region_aggregation(prev_del, "region_name", "delivery_mwh")
                if not prev_agg.empty:
                    merged_g = df_region_with_data.merge(prev_agg, on="region_key", suffixes=("_cur","_prev"))
                    merged_g = merged_g[merged_g["delivery_mwh_prev"] > 0]
                    if not merged_g.empty:
                        prev_safe = merged_g["delivery_mwh_prev"].replace(0, float("nan"))
                        merged_g["growth"] = (merged_g["delivery_mwh_cur"] - merged_g["delivery_mwh_prev"]) / prev_safe * 100
                        fastest = merged_g.loc[merged_g["growth"].idxmax()]
                        growth_region = fastest["region_key"]
                        growth_label  = f"{fastest['growth']:+.1f}%"

        # Grid-level concentration
        median_del = df_region_with_data["delivery_mwh"].median()
        efficient_regions = df_region_with_data[df_region_with_data["delivery_mwh"] >= median_del]
        most_balanced = efficient_regions.iloc[(efficient_regions["delivery_mwh"] - median_del).abs().argsort()[:1]]["region_key"].values[0] if not efficient_regions.empty else "N/A"

        # 2nd highest (diversification)
        second_region = sorted_desc.iloc[1] if len(sorted_desc) >= 2 else sorted_desc.iloc[0]

        _yr_label = str(global_year) if global_year else "All Years"
        _low_twh  = low_region['delivery_mwh'] / 1e3
        _low_unit = "GWh" if _low_twh < 1000 else "TWh"
        _low_val  = f"{_low_twh:.0f} {_low_unit}" if _low_unit == "GWh" else f"{low_region['delivery_mwh']/1e6:.2f} TWh"
        render_intel_summary(
            situation=(f"{top_region['region_key']} leads with {top_region['delivery_mwh']/1e6:.2f} TWh "
                       f"({top_share:.1f}% of total). {growth_region} growing fastest at {growth_label} YoY."),
            impact=(f"{low_region['region_key']} has lowest delivery at {_low_val}. "
                    f"Most balanced distribution: {most_balanced}. "
                    f"2nd largest: {second_region['region_key']} "
                    f"({second_region['delivery_mwh']/1e6:.2f} TWh)."),
            action="Expand interconnection capacity in low-delivery regions; review distribution adequacy.",
            tag=f"Regional Intel — {_yr_label}",
        )

    # ----- Bar chart: top regions (excluding major aggregates) -----
    if not df_region_with_data.empty:
        bar_data = df_region_with_data.sort_values("delivery_mwh", ascending=True).tail(20)
        st.markdown('<div class="section-header">Energy Delivery by Region (MWh)</div>', unsafe_allow_html=True)
        fig_bar = px.bar(
            bar_data, x="delivery_mwh", y="region_key", orientation="h",
            color_discrete_sequence=["#00C2FF"], template="plotly_dark",
            labels={"delivery_mwh": "MWh", "region_key": ""}
        )
        fig_bar.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                              height=420, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No regional delivery data for bar chart.")

    # ----- Pie chart: major grid share (only when All Grids selected) -----
    st.markdown('<div class="section-header">Major Grid Share</div>', unsafe_allow_html=True)
    if global_grid == "All Grids":
        luzon = df_raw[df_raw["region_name"] == "LUZON"]["delivery_mwh"].sum()
        visayas = df_raw[df_raw["region_name"] == "VISAYAS"]["delivery_mwh"].sum()
        mindanao = df_raw[df_raw["region_name"] == "MINDANAO"]["delivery_mwh"].sum()
        grid_shares = pd.DataFrame({
            "Grid": ["Luzon", "Visayas", "Mindanao"],
            "MWh": [luzon, visayas, mindanao]
        })
        grid_shares = grid_shares[grid_shares["MWh"] > 0]
        if not grid_shares.empty:
            fig_pie = px.pie(
                grid_shares, names="Grid", values="MWh",
                hole=0.4, template="plotly_dark",
                color="Grid", color_discrete_map=COLORS
            )
            fig_pie.update_traces(textinfo="percent+label")
            fig_pie.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                  showlegend=False, height=240, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No grid share data available.")
    else:
        st.caption(f"Grid share is shown only when 'All Grids' is selected. Currently viewing: {global_grid}.")

    # ----- Monthly trend (Philippines, unchanged) -----
    st.markdown('<div class="section-header">Monthly Delivery Trend – Philippines (GWh)</div>', unsafe_allow_html=True)
    ph_raw = st.session_state.delivery_df
    ph_mon = (ph_raw[ph_raw["Region"] == "TOTAL PHILIPPINES"]
              .groupby(["Year", "MonthNum", "Month"])["Delivery_MWh"].sum().reset_index()
              .sort_values(["Year", "MonthNum"]))
    if not ph_mon.empty:
        ph_mon["GWh"] = ph_mon["Delivery_MWh"] / 1e3
        years = sorted(ph_mon["Year"].unique(), reverse=True)
        latest_years = years[:5]   # last 5 years
        ph_mon = ph_mon[ph_mon["Year"].isin(latest_years)]
        fig_line = px.line(
            ph_mon, x="MonthNum", y="GWh", color="Year",
            template="plotly_dark", labels={"MonthNum": "Month", "GWh": "GWh"},
            color_discrete_sequence=px.colors.sequential.Blues_r
        )
        fig_line.update_xaxes(
            tickvals=list(range(1, 13)),
            ticktext=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        )
        fig_line.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               height=240, legend_title_text="Year", margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No monthly trend data available.")

    # ----- Annual growth table (major grids) -----
    st.markdown('<div class="section-header">Annual Energy Delivery Growth by Region</div>', unsafe_allow_html=True)
    major = ["TOTAL PHILIPPINES", "LUZON", "VISAYAS", "MINDANAO"]
    major_df = st.session_state.delivery_df
    major_df = major_df[major_df["Region"].isin(major)].groupby(["Region", "Year"])["Delivery_MWh"].sum().reset_index()
    if not major_df.empty:
        pivot = major_df.pivot(index="Region", columns="Year", values="Delivery_MWh")
        year_cols = sorted(pivot.columns)
        display = pd.DataFrame(index=pivot.index)
        for yr in year_cols:
            display[str(yr)] = (pivot[yr] / 1e6).map("{:.2f}".format)
        if len(year_cols) >= 2:
            latest, prev = year_cols[-1], year_cols[-2]
            display[f"Δ {prev}→{latest}"] = ((pivot[latest] - pivot[prev]) / pivot[prev] * 100).map("{:+.1f}%".format)
        st.dataframe(display, use_container_width=True)
    else:
        st.info("No data for growth table.")

    # ── Export & Downloads ────────────────────────────────────────────────────
    st.markdown('<div class="section-header export-header">Export & Downloads</div>', unsafe_allow_html=True)
    _reg_csv  = st.session_state.delivery_df.to_csv(index=False)
    _major_csv = major_df.to_csv(index=False) if not major_df.empty else ""
    _display_csv = display.to_csv() if not major_df.empty and len(year_cols) >= 1 else ""
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        st.download_button("↓ Export Data", _reg_csv,
                           "regional_delivery.csv", "text/csv",
                           use_container_width=True)
    with ec2:
        st.download_button("↓ Export Intelligence Brief", _major_csv,
                           "grid_delivery_summary.csv", "text/csv",
                           use_container_width=True)
    with ec3:
        st.download_button("↓ Export Full Report", _display_csv,
                           "regional_growth_report.csv", "text/csv",
                           use_container_width=True)

    # ── Methodology ───────────────────────────────────────────────────
    with st.expander("Methodology & Data Notes", expanded=False):
        st.markdown(
            '<p style="font-size:13px;color:var(--text-secondary);line-height:1.6">'
            '<b>Data Source:</b> DOE Energy Delivery Per Region dataset. '
            '<b>Region mapping:</b> DOE regional names are normalized to the NGCP grid zone classification '
            '(Luzon, Visayas, Mindanao). '
            '<b>Delivery vs Generation:</b> Delivery figures represent energy consumed by end-users — '
            'lower than gross generation due to transmission and distribution losses. '
            '<b>Health classification:</b> Derived from year-on-year delivery growth against national trend benchmarks.'
            '</p>',
            unsafe_allow_html=True,
        )

# -------------------------------------------------------------------
if __name__ == "__main__":
    pass
