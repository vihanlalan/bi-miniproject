"""Exception reporting: rule and z-score alerts over the latest months."""
import numpy as np
import pandas as pd

from . import kpi
from .config import ALERT_ON_TIME, ALERT_REV_VS_BUDGET, ALERT_Z, TARGETS


def _z(series: pd.Series, window=12):
    """z-score of the last value against the previous `window` values."""
    hist = series.iloc[-window - 1:-1].dropna()
    if len(hist) < 6 or hist.std(ddof=0) == 0:
        return np.nan
    return (series.iloc[-1] - hist.mean()) / hist.std(ddof=0)


def generate(con, months=3) -> pd.DataFrame:
    m = kpi.monthly(con)
    recent = m.tail(months)
    out = []
    for r in recent.itertuples():
        if r.revenue_vs_budget < ALERT_REV_VS_BUDGET:
            out.append((r.ym, "High", "Revenue", f"Revenue at {r.revenue_vs_budget:.0%} of budget"))
        if r.gross_margin_pct < TARGETS["gross_margin_pct"]["target"] - 0.03:
            out.append((r.ym, "Medium", "Margin", f"Gross margin {r.gross_margin_pct:.1%} is under target"))
        if r.marketing_variance > 0.10 * r.marketing_budget:
            out.append((r.ym, "Medium", "Marketing",
                        f"Marketing spend {r.marketing_variance / r.marketing_budget:+.0%} over budget"))

    # vendors under the on-time floor in the latest month
    vm = kpi.vendor_monthly_on_time(con)
    last = vm[vm.ym == m.ym.iloc[-1]]
    for r in last.itertuples():
        if r.on_time_rate < ALERT_ON_TIME:
            out.append((r.ym, "High" if r.on_time_rate < 0.6 else "Medium", "Vendor",
                        f"{r.vendor_name}: on-time delivery {r.on_time_rate:.0%}"))

    # statistical anomalies in channel CAC (latest month vs trailing 12)
    cm = kpi.channel_monthly(con)
    for ch, g in cm.groupby("channel"):
        g = g.sort_values("ym")
        for k in range(months):
            gk = g.iloc[:len(g) - k]
            z = _z(gk.cac)
            if not np.isnan(z) and z > ALERT_Z:
                out.append((gk.ym.iloc[-1], "High", "Marketing",
                            f"{ch} CAC is Rs {gk.cac.iloc[-1]:,.0f}, z-score {z:.1f} vs the prior 12 months"))
    # vendor on-time z-score (catches a drift before the hard floor)
    for v, g in vm.groupby("vendor_name"):
        g = g.sort_values("ym")
        z = _z(g.on_time_rate)
        if not np.isnan(z) and z < -ALERT_Z and g.on_time_rate.iloc[-1] >= ALERT_ON_TIME:
            out.append((g.ym.iloc[-1], "Low", "Vendor", f"{v}: on-time rate drifting down (z {z:.1f})"))
    df = pd.DataFrame(out, columns=["month", "severity", "area", "message"])
    order = {"High": 0, "Medium": 1, "Low": 2}
    return df.sort_values(["severity", "month"], key=lambda s: s.map(order) if s.name == "severity" else s,
                          ascending=[True, False]).reset_index(drop=True)
