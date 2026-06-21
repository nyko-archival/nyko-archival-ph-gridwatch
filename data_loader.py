# data_loader.py
"""
Centralised data loading for PH GridWatch.
All functions return pandas DataFrames. Error handling returns empty DataFrames.
"""

import os
import pandas as pd
import numpy as np
from config import (
    GEN_FILE, SL_FILE, HOURLY_FILE, DELIVERY_FILE,
    GRIDS, MONTHS, RENEWABLE_TYPES, FOSSIL_TYPES
)

# ----------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------
def load_generation():
    """
    Load generation data from Excel.

    Returns:
        DataFrame with columns: Year, Grid, PlantType, Month, MonthNum, Generation_MWh
        Returns empty DataFrame if file not found or parsing fails.
    """
    if not os.path.exists(GEN_FILE):
        return pd.DataFrame()

    try:
        xl = pd.ExcelFile(GEN_FILE)
    except Exception:
        return pd.DataFrame()

    frames = []
    for sheet in xl.sheet_names:
        try:
            year = int(sheet)
        except ValueError:
            continue
        try:
            df = xl.parse(sheet, header=None)
            _parse_gen_sheet(df, year, frames)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()
    out = pd.DataFrame(frames)
    out["Year"] = out["Year"].astype(int)
    out["Generation_MWh"] = pd.to_numeric(out["Generation_MWh"], errors="coerce").fillna(0)
    return out

def _parse_gen_sheet(df, year, frames):
    """Helper: parse one generation sheet and append rows."""
    current_grid = None
    for _, row in df.iterrows():
        val = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        if val in GRIDS:
            current_grid = val
            continue
        if val == "Total Philippines":
            current_grid = "Philippines"
            continue
        if val == "" or current_grid is None:
            continue
        if val in ("nan", "Note:") or val.startswith("National") or val.startswith("20"):
            continue
        monthly_vals = []
        for col in range(1, 13):
            try:
                v = float(row.iloc[col]) if pd.notna(row.iloc[col]) else 0.0
            except (ValueError, TypeError, IndexError):
                v = 0.0
            monthly_vals.append(v)

        if sum(monthly_vals) == 0:
            continue

        for i, month in enumerate(MONTHS):
            frames.append({
                "Year": year,
                "Grid": current_grid,
                "PlantType": val,
                "Month": month,
                "MonthNum": i + 1,
                "Generation_MWh": monthly_vals[i]
            })

# ----------------------------------------------------------------------
# System Loss
# ----------------------------------------------------------------------
def load_system_loss():
    """
    Load system loss data from Excel.

    Returns:
        DataFrame with columns: Grid, Month, Year, SystemLoss_pct
        Returns empty DataFrame if file missing or parsing fails.
    """
    if not os.path.exists(SL_FILE):
        return pd.DataFrame()

    try:
        df = pd.read_excel(SL_FILE, sheet_name="SL Summary 2013-2023", header=None)
    except Exception:
        return pd.DataFrame()

    rows = []
    current_grid = None
    all_grids = GRIDS + ["Philippines"]
    month_abbrevs = ["Jan","Feb","Mar","Apr","May","Jun",
                     "Jul","Aug","Sep","Oct","Nov","Dec","Total"]

    years = []
    year_row_idx = None
    for i, row in df.iterrows():
        numeric = [v for v in row if isinstance(v,(int,float)) and not pd.isna(v) and 2000 < v < 2100]
        if len(numeric) >= 5:
            year_row_idx = i
            years = [int(v) for v in row if isinstance(v,(int,float)) and not pd.isna(v) and 2000 < v < 2100]
            break

    if year_row_idx is None or not years:
        return pd.DataFrame()

    for i, row in df.iterrows():
        if i <= year_row_idx:
            continue
        cell0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        if cell0 in all_grids:
            current_grid = cell0
            continue
        if cell0 not in month_abbrevs or current_grid is None:
            continue
        month_full = cell0
        if cell0 in month_abbrevs[:-1]:  # all except "Total"
            idx = month_abbrevs.index(cell0)
            month_full = MONTHS[idx]

        for j, yr in enumerate(years):
            try:
                val = float(row.iloc[j + 1]) if pd.notna(row.iloc[j + 1]) else np.nan
            except (ValueError, TypeError, IndexError):
                val = np.nan
            rows.append({
                "Grid": current_grid,
                "Month": month_full if cell0 != "Total" else "Total",
                "Year": yr,
                "SystemLoss_pct": val
            })

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["Year"] = out["Year"].astype(int)
    return out

# ----------------------------------------------------------------------
# Hourly Demand
# ----------------------------------------------------------------------
def load_hourly_demand(grid="Luzon"):
    """
    Load hourly demand for a specific grid.

    Args:
        grid: "Luzon", "Visayas", or "Mindanao"

    Returns:
        DataFrame with columns: Date, Hour1..Hour24, DailyPeak_MW, DailyAvg_MW, Year, Month, etc.
        Returns empty DataFrame if file missing.
    """
    if not os.path.exists(HOURLY_FILE):
        return pd.DataFrame()

    sheet_map = {
        "Luzon":    "LUZON HOURLY LOAD 2013-2025",
        "Visayas":  "VISAYAS HOURLY LOAD 2013-2025",
        "Mindanao": "MINDANAO HOURLY LOAD 2013-2025",
    }
    sheet = sheet_map.get(grid, sheet_map["Luzon"])
    try:
        xl = pd.ExcelFile(HOURLY_FILE)
        df = xl.parse(sheet, header=0)
    except Exception:
        return pd.DataFrame()

    df.rename(columns={df.columns[0]: "Date"}, inplace=True)

    def to_date(v):
        if isinstance(v, (int, float)) and not pd.isna(v):
            try:
                return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(v))
            except Exception:
                return pd.NaT
        try:
            return pd.to_datetime(v)
        except Exception:
            return pd.NaT

    df["Date"] = df["Date"].apply(to_date)
    df = df[df["Date"].notna()].copy()
    if df.empty:
        return df
    df["Year"]  = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["MonthName"] = df["Date"].dt.strftime("%B")
    df["DayOfWeek"] = df["Date"].dt.day_name()

    numeric_cols = df.columns[1:25]
    df["DailyPeak_MW"] = df[numeric_cols].apply(pd.to_numeric, errors="coerce").max(axis=1)
    df["DailyAvg_MW"]  = df[numeric_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)
    return df

def load_hourly_demand_all():
    """Load hourly demand for all grids and concatenate."""
    frames = []
    for grid in GRIDS:
        df = load_hourly_demand(grid)
        if not df.empty:
            df["Grid"] = grid
            frames.append(df)
    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame()

# ----------------------------------------------------------------------
# Energy Delivery
# ----------------------------------------------------------------------
def load_delivery():
    """Load energy delivery per region."""
    if not os.path.exists(DELIVERY_FILE):
        return pd.DataFrame()

    try:
        xl = pd.ExcelFile(DELIVERY_FILE)
    except Exception:
        return pd.DataFrame()

    frames = []
    for sheet in xl.sheet_names:
        try:
            year = int(sheet)
        except ValueError:
            continue
        try:
            df = xl.parse(sheet, header=None)
            _parse_delivery_sheet(df, year, frames)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()
    out = pd.DataFrame(frames)
    out["Year"] = out["Year"].astype(int)
    out["Delivery_MWh"] = pd.to_numeric(out["Delivery_MWh"], errors="coerce").fillna(0)
    return out

def _parse_delivery_sheet(df, year, frames):
    skip = {"Energy Delivery Per Region, in MWh", str(year), "", "nan"}
    month_cols_found = False
    month_col_indices = []

    for _, row in df.iterrows():
        cell0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        if "January" in str(row.values):
            month_col_indices = []
            for ci, v in enumerate(row):
                if str(v).strip() in MONTHS:
                    month_col_indices.append((ci, str(v).strip()))
            month_cols_found = True
            continue
        if not month_cols_found or cell0 in skip:
            continue
        for ci, month in month_col_indices:
            try:
                val = float(row.iloc[ci]) if pd.notna(row.iloc[ci]) else 0.0
            except (ValueError, TypeError):
                val = 0.0
            if val == 0.0:
                continue
            frames.append({
                "Year": year,
                "Region": cell0,
                "Month": month,
                "MonthNum": MONTHS.index(month) + 1,
                "Delivery_MWh": val
            })