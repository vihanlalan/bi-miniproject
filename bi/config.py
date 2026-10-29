"""Shared constants. Targets here play the role of the 'strategy' in the scorecard."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "warehouse.db"
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"

SEED = 42
START = "2024-01-01"
END = "2025-12-31"
CURRENT_YEAR = 2025
PROMISED_DAYS = 6          # delivery promise made to customers
RETURN_HANDLING_RATE = 0.15  # reverse logistics cost as share of the returned order value
CHANNELS = ["Search", "Social", "Email", "Affiliate"]  # paid channels
ALL_CHANNELS = CHANNELS + ["Organic"]

# Scorecard targets (FY2025). direction: "higher" or "lower" is better.
TARGETS = {
    "revenue_vs_budget": {"target": 1.00, "direction": "higher"},
    "gross_margin_pct": {"target": 0.28, "direction": "higher"},
    "marketing_roi": {"target": 2.0, "direction": "higher"},
    "repeat_customer_rate": {"target": 0.45, "direction": "higher"},
    "annual_retention": {"target": 0.50, "direction": "higher"},
    "on_time_rate": {"target": 0.85, "direction": "higher"},
    "return_rate": {"target": 0.08, "direction": "lower"},
    "new_product_rev_share": {"target": 0.15, "direction": "higher"},
    "new_customer_growth": {"target": 0.10, "direction": "higher"},
}

# Alert thresholds for exception reporting
ALERT_REV_VS_BUDGET = 0.90
ALERT_ON_TIME = 0.80
ALERT_Z = 2.0
