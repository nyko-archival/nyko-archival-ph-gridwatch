# config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

GEN_FILE = os.path.join(DATA_DIR, "Gross_Generation_Per_Plant_Type__2_.xlsx")
SL_FILE = os.path.join(DATA_DIR, "System_Loss__2_.xlsx")
HOURLY_FILE = os.path.join(DATA_DIR, "Hourly_Demand__2_.xlsx")
DELIVERY_FILE = os.path.join(DATA_DIR, "Energy_Delivery_Per_Region__2_.xlsx")

GRIDS = ["Luzon", "Visayas", "Mindanao"]
MONTHS = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]
RENEWABLE_TYPES = ["Geothermal","Hydro","Renewable (Wind)","Renewable (Solar)",
                   "Renewable (Biomass)","Bio-Gas"]
FOSSIL_TYPES = ["Coal","Diesel","Gas Turbine","Combined Cycle / Natural Gas",
                "Thermal","Natural Gas"]

# RE sub-categories: Variable (intermittent) vs Dispatchable (firm/baseload)
VARIABLE_RE_TYPES     = ["Renewable (Wind)", "Renewable (Solar)"]
DISPATCHABLE_RE_TYPES = ["Geothermal", "Hydro", "Renewable (Biomass)", "Bio-Gas"]

TARGET_RE_2030 = 35.0
TARGET_RE_2040 = 50.0
TARGET_SYSTEM_LOSS = 2.0

# Economic cost proxy for lost energy (WESM average wholesale price)
WESM_MARGINAL_COST_PER_KWH = 5.50  # ₱/kWh

DEFAULT_YEAR = 2023
CACHE_TTL = 3600

COLORS = {
    "Luzon": "#00C2FF",
    "Visayas": "#F4A261",
    "Mindanao": "#2DC653",
    "Philippines": "#C77DFF",
}
RE_COLOR = "#2DC653"
NRE_COLOR = "#EF4444"