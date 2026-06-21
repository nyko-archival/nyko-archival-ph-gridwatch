# utils/calculations.py
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from config import RENEWABLE_TYPES

def classify_plant(plant_type: str) -> str:
    return "Renewable" if plant_type in RENEWABLE_TYPES else "Non-Renewable"

def compute_energy_security_score(re_pct: float, demand_growth_pct: float, sys_loss_pct: float):
    # Supply-Demand Balance: proxy via demand growth rate
    # (low demand growth vs capacity = better balance; not a true reserve margin)
    supply_balance = max(0, min(100, 100 - (demand_growth_pct - 2) * 10))
    # Generation Diversity: RE share index (maxes at 50% RE = score 100)
    diversity = min(100, re_pct * 2)
    # System Efficiency: inverse of transmission losses
    efficiency = max(0, min(100, 100 - sys_loss_pct * 20))
    score = 0.40 * supply_balance + 0.40 * diversity + 0.20 * efficiency
    return round(score, 1), round(supply_balance, 1), round(diversity, 1), round(efficiency, 1)

# ── Dynamic content generators ────────────────────────────────────────────────

def generate_briefing(avg_sl: float, re_pct: float, risk_count: int,
                      re_gap: float, target_sl: float, target_re: float) -> str:
    status = ("under elevated operational risk" if risk_count >= 2
              else ("under watch" if risk_count == 1 else "operationally stable"))
    if avg_sl > target_sl:
        loss_clause = (f"transmission losses at {avg_sl:.2f}% are "
                       f"{avg_sl - target_sl:.2f}pp above the DOE target")
    else:
        loss_clause = f"transmission losses at {avg_sl:.2f}% are within the DOE target"
    if re_gap > 0:
        re_clause = (f"renewable deployment at {re_pct:.1f}% is "
                     f"{re_gap:.1f}pp below the 2030 trajectory")
    else:
        re_clause = f"renewable share at {re_pct:.1f}% has met the 2030 target"
    loss_clause_cap = loss_clause[0].upper() + loss_clause[1:]
    return f"The Philippine power system is {status}. {loss_clause_cap}; {re_clause}."

def gen_commentary(gen_trend: float) -> str:
    if gen_trend > 6:
        return f"Generation surged {gen_trend:.1f}% YoY — assess fuel mix shift."
    if gen_trend > 2:
        return f"Generation grew {gen_trend:.1f}% YoY — on normal trajectory."
    if gen_trend >= -2:
        return f"Generation stable ({gen_trend:+.1f}% YoY)."
    if gen_trend >= -6:
        return f"Generation declined {abs(gen_trend):.1f}% — monitor capacity margins."
    return f"Generation fell {abs(gen_trend):.1f}% YoY — requires investigation."

def demand_commentary(dem_trend: float) -> str:
    if dem_trend > 8:
        return f"Peak demand surging {dem_trend:.1f}% — capacity adequacy risk elevated."
    if dem_trend > 5:
        return f"Peak demand growing {dem_trend:.1f}% — plan capacity additions."
    if dem_trend > 2:
        return f"Demand expanding {dem_trend:.1f}% — within manageable range."
    if dem_trend >= 0:
        return f"Demand growth {dem_trend:.1f}% — stable conditions."
    return f"Demand contracted {abs(dem_trend):.1f}% — assess economic factors."

def health_commentary(health_score: float, avg_sl: float, target_sl: float) -> str:
    if health_score >= 85:
        return f"System operating efficiently. Loss {avg_sl:.2f}% — within target."
    if health_score >= 70:
        return f"System under watch. Loss {avg_sl:.2f}% vs {target_sl}% target."
    return f"System under stress. Loss {avg_sl:.2f}% — {avg_sl - target_sl:.2f}pp above target."

def sec_commentary(sec_score: float) -> str:
    if sec_score >= 70:
        return "Supply outlook secure — demand and RE indicators balanced."
    if sec_score >= 50:
        return "Supply outlook moderate — demand stress or RE shortfall present."
    return "Supply outlook vulnerable — demand growth exceeds RE development pace."

def compute_growth_rate(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current - previous) / previous * 100

def filter_by_global_selection(df, year_col, grid_col, global_year, global_grid, grid_list):
    if df.empty:
        return df
    result = df[df[year_col] == global_year]
    if global_grid != "All Grids" and grid_col in result.columns:
        result = result[result[grid_col] == global_grid]
    return result

def forecast_annual_peak(historical_df, year_col, peak_col, years_ahead=2):
    df = historical_df[[year_col, peak_col]].dropna().copy()
    if len(df) < 3:
        return np.array([]), np.array([]), np.array([]), np.array([])
    X = df[year_col].values.reshape(-1, 1)
    y = df[peak_col].values
    model = LinearRegression()
    model.fit(X, y)
    last_year = df[year_col].max()
    future_years = np.arange(last_year + 1, last_year + years_ahead + 1).reshape(-1, 1)
    pred = model.predict(future_years)
    residuals = y - model.predict(X)
    std_resid = np.std(residuals)
    margin = 1.96 * std_resid
    return future_years.flatten(), pred, pred - margin, pred + margin

def forecast_re_trajectory(re_annual_df: pd.DataFrame, year_col: str, re_col: str,
                           target_year: int = 2030):
    """Linear regression projection of RE share percentage.

    Returns (projected_pct, slope_pp_per_yr, ci_low, ci_high) at target_year,
    or (None, None, None, None) if fewer than 3 data points.
    """
    df = re_annual_df[[year_col, re_col]].dropna().copy()
    if len(df) < 3:
        return None, None, None, None
    X = df[year_col].values.reshape(-1, 1)
    y = df[re_col].values
    model = LinearRegression()
    model.fit(X, y)
    slope = float(model.coef_[0])
    projected = float(model.predict([[target_year]])[0])
    residuals = y - model.predict(X)
    margin = 1.96 * float(np.std(residuals))
    return projected, slope, projected - margin, projected + margin

def compute_hhi(shares_pct: list) -> float:
    """Herfindahl-Hirschman Index for fuel concentration.

    Range 0–10 000. Higher = more concentrated.
    <1500: diverse, 1500–2500: moderate, >2500: concentrated.
    """
    return round(sum((s / 100) ** 2 * 10000 for s in shares_pct if s > 0), 0)

def detect_loss_anomalies(monthly_df: pd.DataFrame, grid_col: str, year_col: str,
                           month_col: str, loss_col: str, sigma: float = 2.0) -> pd.DataFrame:
    """Flag months where system loss deviates ≥ sigma std devs from the historical seasonal mean.

    Returns a DataFrame with columns: Grid, Month, Year, Loss_pct,
    Historical_Mean, Historical_Std, Z_Score, Direction.
    """
    results = []
    for (grid, month), grp in monthly_df.groupby([grid_col, month_col]):
        if len(grp) < 3:
            continue
        hist_mean = grp[loss_col].mean()
        hist_std = grp[loss_col].std()
        if hist_std == 0:
            continue
        for _, row in grp.iterrows():
            z = (row[loss_col] - hist_mean) / hist_std
            if abs(z) >= sigma:
                results.append({
                    "Grid": grid, "Month": month, "Year": int(row[year_col]),
                    "Loss_pct": round(float(row[loss_col]), 3),
                    "Historical_Mean": round(float(hist_mean), 3),
                    "Historical_Std": round(float(hist_std), 3),
                    "Z_Score": round(float(z), 2),
                    "Direction": "High" if z > 0 else "Low",
                })
    if not results:
        return pd.DataFrame(columns=["Grid","Month","Year","Loss_pct",
                                      "Historical_Mean","Historical_Std","Z_Score","Direction"])
    return pd.DataFrame(results).sort_values(["Year","Grid","Month"])