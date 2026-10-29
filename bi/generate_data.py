"""Synthetic data for a mid-size online retailer ("ShopSphere").

The data is simulated, not real. Two business problems are injected on purpose so the
dashboards and alerts have something to find:
  1. Social-media acquisition gets expensive from Sep 2025 (spend stays, sign-ups drop).
  2. Vendor "Evergreen Imports" starts delivering about 3 days late from Oct 2025.
A small amount of dirty data (duplicates, nulls, negative quantities) is also added so
the ETL step has real cleaning to do.
"""
import numpy as np
import pandas as pd

from .config import (ALL_CHANNELS, CHANNELS, END, PROMISED_DAYS, RAW_DIR, SEED, START)

VENDORS = [
    # name, base lead time (days), defect rate, cost index
    ("Apex Components", 3.0, 0.02, 1.00),
    ("BlueLine Supply", 4.0, 0.03, 0.92),
    ("Cedar Trading", 5.0, 0.05, 0.85),
    ("Delta Source", 3.5, 0.02, 1.10),
    ("Evergreen Imports", 4.5, 0.04, 0.88),
    ("Fulcrum Goods", 5.5, 0.06, 0.80),
]
# category: (base cost range, gross margin at list price, base return rate)
CATEGORIES = {
    "Electronics": ((40, 220), 0.22, 0.07),
    "Home & Kitchen": ((10, 80), 0.38, 0.05),
    "Fashion": ((8, 60), 0.45, 0.12),
    "Beauty": ((5, 40), 0.50, 0.04),
    "Sports": ((15, 120), 0.33, 0.06),
}
SEASON = {1: 0.85, 2: 0.80, 3: 0.90, 4: 0.92, 5: 0.95, 6: 1.00,
          7: 0.95, 8: 0.92, 9: 1.00, 10: 1.10, 11: 1.35, 12: 1.45}
PROMO_MONTHS = {6, 11, 12}
CHANNEL_MIX = {"Search": 0.35, "Social": 0.25, "Email": 0.12, "Affiliate": 0.13, "Organic": 0.15}
BASE_CAC = {"Search": 2400.0, "Social": 2000.0, "Email": 900.0, "Affiliate": 2800.0}  # Rs per sign-up
PRICE_SCALE = 25  # converts the base cost ranges below into rupees


def _vendors():
    df = pd.DataFrame(VENDORS, columns=["vendor_name", "base_lead_days", "defect_rate", "cost_index"])
    df.insert(0, "vendor_id", range(1, len(df) + 1))
    return df


def _products(rng, vendors):
    rows = []
    cats = list(CATEGORIES)
    for pid in range(1, 41):
        cat = cats[(pid - 1) % len(cats)]
        (lo, hi), margin, _ = CATEGORIES[cat]
        v = vendors.iloc[rng.integers(0, len(vendors))]
        cost = round(rng.uniform(lo, hi) * PRICE_SCALE * v.cost_index, 2)
        price = round(cost / (1 - margin) * rng.uniform(0.95, 1.05), 2)
        # about a quarter of the catalogue launches during the 24 months
        launch = (pd.Timestamp("2023-06-01") if rng.random() > 0.25
                  else pd.Timestamp(START) + pd.Timedelta(days=int(rng.integers(30, 600))))
        rows.append((pid, f"{cat} item {pid:02d}", cat, int(v.vendor_id), cost, price, launch.date()))
    return pd.DataFrame(rows, columns=["product_id", "product_name", "category", "vendor_id",
                                        "unit_cost", "list_price", "launch_date"])


def _customers(rng, n=3500):
    months = pd.period_range(START, END, freq="M")
    w = np.linspace(1.0, 1.9, len(months)) * np.array([SEASON[m.month] for m in months])
    w /= w.sum()
    m_idx = rng.choice(len(months), size=n, p=w)
    day = rng.integers(0, 28, size=n)
    signup = [months[i].to_timestamp() + pd.Timedelta(days=int(d)) for i, d in zip(m_idx, day)]
    ch = rng.choice(list(CHANNEL_MIX), size=n, p=list(CHANNEL_MIX.values()))
    df = pd.DataFrame({
        "customer_id": np.arange(1, n + 1),
        "signup_date": signup,
        "region": rng.choice(["North", "South", "East", "West"], size=n, p=[0.28, 0.27, 0.2, 0.25]),
        "channel": ch,
    })
    df["signup_ym"] = df.signup_date.dt.strftime("%Y-%m")
    return df


def _marketing(rng, customers):
    """Spend is set from the sign-ups the plan expected; the Social drop happens after."""
    # Expected sign-ups before the injected Social problem
    exp = customers.groupby(["signup_ym", "channel"]).size().rename("n").reset_index()
    rows = []
    for ym in pd.period_range(START, END, freq="M").strftime("%Y-%m"):
        for ch in CHANNELS:
            n = exp[(exp.signup_ym == ym) & (exp.channel == ch)].n.sum()
            spend = n * BASE_CAC[ch] * rng.uniform(0.9, 1.1)
            rows.append((ym, ch, round(spend, 2)))
    mk = pd.DataFrame(rows, columns=["ym", "channel", "spend"])
    # Inject: Social sign-ups drop 55% for Sep-Nov 2025 while spend stays on plan
    bad = customers.channel.eq("Social") & customers.signup_ym.isin(["2025-09", "2025-10", "2025-11"])
    drop = bad & (rng.random(len(customers)) < 0.55)
    customers = customers[~drop].copy()
    nc = customers.groupby(["signup_ym", "channel"]).size().rename("new_customers").reset_index()
    mk = mk.merge(nc, left_on=["ym", "channel"], right_on=["signup_ym", "channel"], how="left"
                  ).drop(columns="signup_ym").fillna({"new_customers": 0})
    mk["new_customers"] = mk.new_customers.astype(int)
    return mk, customers


def _orders(rng, customers, products, vendors):
    months = pd.period_range(START, END, freq="M")
    pop = rng.zipf(1.6, size=len(products)).astype(float)
    pop = np.minimum(pop, 8)
    prod_w = pop / pop.sum()
    vend = vendors.set_index("vendor_id")
    prod = products.set_index("product_id")
    lines, oid, lid = [], 0, 0
    for c in customers.itertuples():
        lam = rng.gamma(1.4, 0.32)                       # orders per active month
        life = rng.exponential(13)                       # months before the customer goes quiet
        start_m = pd.Period(c.signup_date, "M")
        for m in months[months >= start_m]:
            age = (m - start_m).n
            if age > life:
                break
            k = rng.poisson(lam * SEASON[m.month] * (1.4 if age == 0 else 1.0))
            for _ in range(k):
                oid += 1
                day = pd.Timestamp(m.start_time) + pd.Timedelta(days=int(rng.integers(0, m.days_in_month)))
                if day < c.signup_date or day > pd.Timestamp(END):
                    day = max(c.signup_date, pd.Timestamp(m.start_time))
                disc = rng.uniform(0.10, 0.20) if m.month in PROMO_MONTHS else rng.choice([0, 0, 0.05])
                for pid in rng.choice(products.product_id.values, size=rng.integers(1, 4), p=prod_w, replace=False):
                    lid += 1
                    p = prod.loc[pid]
                    v = vend.loc[p.vendor_id]
                    late = 3 if (v.vendor_name == "Evergreen Imports" and day >= pd.Timestamp("2025-10-01")) else 0
                    days = max(1, int(round(v.base_lead_days + late + rng.normal(0, 1.2))))
                    ret_p = CATEGORIES[p.category][2] + v.defect_rate * 0.5
                    lines.append((lid, oid, day, c.customer_id, int(pid), int(rng.integers(1, 4)),
                                  p.list_price, round(disc, 2), PROMISED_DAYS, days,
                                  int(rng.random() < ret_p)))
    cols = ["line_id", "order_id", "order_date", "customer_id", "product_id", "qty", "unit_price",
            "discount_rate", "promised_days", "delivery_days", "returned"]
    return pd.DataFrame(lines, columns=cols)


def _budget(sales):
    """Plan figures. Finance set the plan ahead of time, so it is the actual run-rate with a
    planning error of -7% to +10% per month (it does not know about the injected problems)."""
    s = sales.copy()
    s["ym"] = s.order_date.dt.strftime("%Y-%m")
    s["rev"] = s.qty * s.unit_price * (1 - s.discount_rate)
    m = s.groupby("ym").rev.sum()
    rng = np.random.default_rng(SEED + 7)
    b = pd.DataFrame({"ym": m.index, "revenue_budget": (m.values * rng.uniform(0.93, 1.10, len(m))).round(2)})
    b["marketing_budget"] = (b.revenue_budget * 0.07).round(2)
    return b


def _dirty(sales, rng):
    d = sales.copy()
    dup = d.sample(45, random_state=1)
    nulls = d.sample(70, random_state=2).index
    d.loc[nulls, "delivery_days"] = np.nan
    neg = d.sample(12, random_state=3).index
    d.loc[neg, "qty"] = -d.loc[neg, "qty"]
    return pd.concat([d, dup], ignore_index=True)


def generate(out_dir=RAW_DIR):
    rng = np.random.default_rng(SEED)
    out_dir.mkdir(parents=True, exist_ok=True)
    vendors = _vendors()
    products = _products(rng, vendors)
    customers = _customers(rng)
    marketing, customers = _marketing(rng, customers)
    sales = _orders(rng, customers, products, vendors)
    budget = _budget(sales)
    sales_raw = _dirty(sales, rng)
    customers = customers.drop(columns="signup_ym")
    for name, df in {"vendors": vendors, "products": products, "customers": customers,
                     "sales": sales_raw, "marketing": marketing, "budget": budget}.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    return {k: len(v) for k, v in {"customers": customers, "sales_lines": sales_raw, "products": products}.items()}


if __name__ == "__main__":
    print(generate())
