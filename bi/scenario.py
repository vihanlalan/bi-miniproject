"""Decision engineering: what-if model, sensitivity (tornado), goal seek and Monte Carlo risk.

The model projects next-year contribution (gross profit minus marketing) from the latest
12 months. Elasticities are assumptions, not estimates from this data, and are exposed as
inputs so a user can challenge them.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from .config import CURRENT_YEAR, RETURN_HANDLING_RATE, SEED


@dataclass(frozen=True)
class Baseline:
    gross_list: float      # sales at list price
    discount_rate: float   # share of list price given away
    cogs: float            # cost of all lines sold (before returns)
    return_rate: float     # share of net revenue returned
    marketing: float
    new_cust_share: float  # share of revenue from customers acquired this year


@dataclass(frozen=True)
class Levers:
    price_change: float = 0.0       # +0.05 = list prices up 5%
    discount_change: float = 0.0    # +0.02 = two more points of discount
    marketing_change: float = 0.0   # +0.10 = 10% more spend
    return_rate_change: float = 0.0  # absolute points
    cogs_change: float = 0.0        # supplier cost shock, +0.03 = 3% dearer
    price_elasticity: float = -1.3
    marketing_exponent: float = 0.6  # diminishing returns: new customers ~ spend^0.6
    demand_shock: float = 0.0


def baseline_from_db(con, year=CURRENT_YEAR) -> Baseline:
    s = pd.read_sql(f"""SELECT SUM(gross_sales) g, SUM(discount_amt) d, SUM(cogs) c, SUM(net_revenue) n,
                               SUM(net_revenue*returned) rn FROM v_sales WHERE year={year}""", con).iloc[0]
    new = pd.read_sql(f"""SELECT SUM(realised_revenue) r FROM v_sales
                          WHERE year={year} AND signup_date >= '{year}-01-01'""", con).r[0]
    tot = pd.read_sql(f"SELECT SUM(realised_revenue) r FROM v_sales WHERE year={year}", con).r[0]
    mk = pd.read_sql(f"SELECT SUM(spend) s FROM fact_marketing WHERE ym LIKE '{year}-%'", con).s[0]
    return Baseline(float(s.g), float(s.d / s.g), float(s.c), float(s.rn / s.n), float(mk), float(new / tot))


def project(b: Baseline, l: Levers = Levers()) -> dict:
    disc = max(0.0, min(0.9, b.discount_rate + l.discount_change))
    price_factor = (1 + l.price_change) * (1 - disc) / (1 - b.discount_rate)
    units = price_factor ** l.price_elasticity
    mkt = 1 + b.new_cust_share * ((1 + l.marketing_change) ** l.marketing_exponent - 1)
    units *= mkt * (1 + l.demand_shock)
    net = b.gross_list * units * (1 + l.price_change) * (1 - disc)
    cogs = b.cogs * units * (1 + l.cogs_change)
    r = max(0.0, b.return_rate + l.return_rate_change)
    realised = net * (1 - r)
    gross_profit = realised - cogs * (1 - r) - net * r * RETURN_HANDLING_RATE
    marketing = b.marketing * (1 + l.marketing_change)
    return {"revenue": realised, "gross_profit": gross_profit, "marketing": marketing,
            "contribution": gross_profit - marketing, "units_index": units}


def compare(b: Baseline, scenarios: dict) -> pd.DataFrame:
    base = project(b)
    rows = []
    for name, lev in scenarios.items():
        p = project(b, lev)
        rows.append({"scenario": name, **p,
                     "revenue_delta": p["revenue"] / base["revenue"] - 1,
                     "contribution_delta": p["contribution"] / base["contribution"] - 1})
    return pd.DataFrame(rows)


DEFAULT_SCENARIOS = {
    "Baseline (no change)": Levers(),
    "Price +3%": Levers(price_change=0.03),
    "Price -3%": Levers(price_change=-0.03),
    "Marketing +20%": Levers(marketing_change=0.20),
    "Marketing -20%": Levers(marketing_change=-0.20),
    "Discount +3 pts": Levers(discount_change=0.03),
    "Supplier costs +5%": Levers(cogs_change=0.05),
    "Cut returns by 2 pts": Levers(return_rate_change=-0.02),
    "Combined: price +2%, marketing +10%, returns -2 pts":
        Levers(price_change=0.02, marketing_change=0.10, return_rate_change=-0.02),
}


def tornado(b: Baseline, swing=0.10) -> pd.DataFrame:
    """Change in contribution when each driver moves by +/- swing (relative)."""
    base = project(b)["contribution"]
    d = Levers()
    tests = {
        "List price (+/-10%)": (replace(d, price_change=-swing), replace(d, price_change=swing)),
        "Supplier cost (+/-10%)": (replace(d, cogs_change=swing), replace(d, cogs_change=-swing)),
        "Marketing spend (+/-10%)": (replace(d, marketing_change=-swing), replace(d, marketing_change=swing)),
        "Return rate (+/-2 pts)": (replace(d, return_rate_change=0.02), replace(d, return_rate_change=-0.02)),
        "Discount (+/-2 pts)": (replace(d, discount_change=0.02), replace(d, discount_change=-0.02)),
        "Underlying demand (+/-5%)": (replace(d, demand_shock=-0.05), replace(d, demand_shock=0.05)),
    }
    rows = []
    for k, (lo, hi) in tests.items():
        rows.append((k, project(b, lo)["contribution"] - base, project(b, hi)["contribution"] - base))
    df = pd.DataFrame(rows, columns=["driver", "downside", "upside"])
    df["range"] = (df.upside - df.downside).abs()
    return df.sort_values("range", ascending=False).reset_index(drop=True)


def breakeven_elasticity(b: Baseline, price_change=0.03) -> float:
    """Elasticity at which a price rise stops adding contribution (more negative = customers react more)."""
    base = project(b)["contribution"]
    f = lambda e: project(b, Levers(price_change=price_change, price_elasticity=e))["contribution"] - base
    return float(brentq(f, -6.0, -0.1))


def goal_seek_price(b: Baseline, target_contribution: float, base_levers: Levers = Levers()):
    """Price change needed to reach a contribution target (None if not reachable in -20%..+30%)."""
    f = lambda p: project(b, replace(base_levers, price_change=p))["contribution"] - target_contribution
    lo, hi = -0.20, 0.30
    # contribution is not monotonic in price when elasticity is high, so scan first
    grid = np.linspace(lo, hi, 101)
    vals = np.array([f(p) for p in grid])
    idx = np.where(np.sign(vals[:-1]) != np.sign(vals[1:]))[0]
    if len(idx) == 0:
        return None
    i = idx[0]
    return float(brentq(f, grid[i], grid[i + 1]))


def monte_carlo(b: Baseline, plan: Levers, n=10_000, seed=SEED) -> dict:
    """Run the plan with uncertain assumptions and return the profit distribution."""
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for i in range(n):
        lev = replace(plan,
                      price_elasticity=rng.normal(-1.3, 0.3),
                      marketing_exponent=rng.uniform(0.4, 0.8),
                      demand_shock=rng.normal(0.0, 0.06),
                      cogs_change=plan.cogs_change + rng.normal(0.02, 0.03),
                      return_rate_change=plan.return_rate_change + rng.normal(0, 0.01))
        out[i] = project(b, lev)["contribution"]
    base = project(b)["contribution"]
    return {"samples": out, "mean": float(out.mean()), "p5": float(np.percentile(out, 5)),
            "p50": float(np.median(out)), "p95": float(np.percentile(out, 95)),
            "baseline": base, "prob_below_baseline": float((out < base).mean()),
            "expected_shortfall_5": float(out[out <= np.percentile(out, 5)].mean())}
