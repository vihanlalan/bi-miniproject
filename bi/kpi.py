"""KPI layer: SQL against the warehouse, returned as DataFrames."""
import pandas as pd

from .config import CURRENT_YEAR, TARGETS


def monthly(con) -> pd.DataFrame:
    """One row per month: revenue, margin, orders, AOV, returns, delivery, budget, marketing."""
    sales = pd.read_sql("""
        SELECT ym,
               SUM(realised_revenue) AS revenue,
               SUM(gross_profit) AS gross_profit,
               COUNT(DISTINCT order_id) AS orders,
               COUNT(DISTINCT customer_id) AS active_customers,
               SUM(net_revenue * returned) / SUM(net_revenue) AS return_rate,
               AVG(on_time) AS on_time_rate,
               SUM(discount_amt) / SUM(gross_sales) AS discount_rate
        FROM v_sales GROUP BY ym ORDER BY ym""", con)
    mk = pd.read_sql("SELECT ym, SUM(spend) AS marketing_spend, SUM(new_customers) AS paid_new_customers "
                     "FROM fact_marketing GROUP BY ym", con)
    bud = pd.read_sql("SELECT * FROM fact_budget", con)
    df = sales.merge(mk, on="ym").merge(bud, on="ym")
    df["gross_margin_pct"] = df.gross_profit / df.revenue
    df["aov"] = df.revenue / df.orders
    df["contribution"] = df.gross_profit - df.marketing_spend
    df["revenue_vs_budget"] = df.revenue / df.revenue_budget
    df["budget_variance"] = df.revenue - df.revenue_budget
    df["marketing_variance"] = df.marketing_spend - df.marketing_budget
    return df


def channel_performance(con, year=CURRENT_YEAR) -> pd.DataFrame:
    """Spend, sign-ups, CAC and first-year revenue ROI by acquisition channel."""
    mk = pd.read_sql(f"SELECT channel, SUM(spend) spend, SUM(new_customers) new_customers "
                     f"FROM fact_marketing WHERE ym LIKE '{year}-%' GROUP BY channel", con)
    rev = pd.read_sql(f"""SELECT channel, SUM(gross_profit) gross_profit, SUM(realised_revenue) revenue
                          FROM v_sales WHERE year={year} AND signup_date >= '{year}-01-01' GROUP BY channel""", con)
    df = mk.merge(rev, on="channel", how="left")
    df["cac"] = df.spend / df.new_customers
    df["roi"] = df.revenue / df.spend
    df["profit_roi"] = df.gross_profit / df.spend
    return df


def channel_monthly(con) -> pd.DataFrame:
    df = pd.read_sql("SELECT ym, channel, spend, new_customers FROM fact_marketing", con)
    df["cac"] = df.spend / df.new_customers.where(df.new_customers > 0)
    return df


def category_performance(con, year=CURRENT_YEAR) -> pd.DataFrame:
    return pd.read_sql(f"""
        SELECT category, SUM(realised_revenue) revenue, SUM(gross_profit) gross_profit,
               SUM(gross_profit)/SUM(realised_revenue) margin_pct,
               SUM(net_revenue*returned)/SUM(net_revenue) return_rate
        FROM v_sales WHERE year={year} GROUP BY category ORDER BY revenue DESC""", con)


def vendor_performance(con, year=CURRENT_YEAR) -> pd.DataFrame:
    return pd.read_sql(f"""
        SELECT v.vendor_id, v.vendor_name, v.cost_index,
               AVG(s.on_time) on_time_rate, AVG(s.delivery_days) avg_delivery_days,
               SUM(s.net_revenue*s.returned)/SUM(s.net_revenue) return_rate,
               SUM(s.realised_revenue) revenue
        FROM v_sales s JOIN dim_vendor v ON v.vendor_id = s.vendor_id
        WHERE s.year={year} GROUP BY v.vendor_id ORDER BY v.vendor_id""", con)


def vendor_monthly_on_time(con) -> pd.DataFrame:
    return pd.read_sql("SELECT ym, vendor_name, AVG(on_time) on_time_rate FROM v_sales GROUP BY ym, vendor_name", con)


def paid_first_year_profit(con, year=CURRENT_YEAR) -> float:
    """Gross profit earned in `year` by customers who signed up in `year` through a paid channel."""
    return float(pd.read_sql(f"""SELECT SUM(gross_profit) p FROM v_sales WHERE year={year}
                                 AND signup_date >= '{year}-01-01' AND channel != 'Organic'""", con).p[0])


def annual_summary(con, year=CURRENT_YEAR) -> dict:
    m = monthly(con)
    y = m[m.ym.str.startswith(str(year))]
    rev, gp = y.revenue.sum(), y.gross_profit.sum()
    spend = y.marketing_spend.sum()
    prev = m[m.ym.str.startswith(str(year - 1))]
    return {
        "revenue": rev, "revenue_budget": y.revenue_budget.sum(),
        "revenue_vs_budget": rev / y.revenue_budget.sum(),
        "prior_year_revenue": prev.revenue.sum(), "yoy_growth": rev / prev.revenue.sum() - 1,
        "gross_profit": gp, "gross_margin_pct": gp / rev,
        "marketing_spend": spend, "marketing_budget": y.marketing_budget.sum(),
        "marketing_roi": paid_first_year_profit(con, year) / spend, "contribution": gp - spend,
        "orders": int(y.orders.sum()), "aov": rev / y.orders.sum(),
        "return_rate": float(pd.read_sql(f"SELECT SUM(net_revenue*returned)/SUM(net_revenue) r FROM v_sales WHERE year={year}", con).r[0]),
        "on_time_rate": float(pd.read_sql(f"SELECT AVG(on_time) r FROM v_sales WHERE year={year}", con).r[0]),
    }


def customer_kpis(con, year=CURRENT_YEAR) -> dict:
    """Repeat rate, retention and new-customer growth, all at the customer level."""
    o = pd.read_sql("SELECT customer_id, ym, year FROM v_sales GROUP BY customer_id, order_id", con)
    cur = o[o.year == year]
    orders_per_cust = cur.groupby("customer_id").size()
    repeat = (orders_per_cust >= 2).mean()
    prev_active = set(o[o.year == year - 1].customer_id)
    retention = len(prev_active & set(cur.customer_id)) / len(prev_active)
    sg = pd.read_sql("SELECT substr(signup_date,1,4) y, COUNT(*) n FROM dim_customer GROUP BY y", con).set_index("y").n
    growth = sg[str(year)] / sg[str(year - 1)] - 1
    return {"repeat_customer_rate": float(repeat), "annual_retention": float(retention),
            "new_customer_growth": float(growth), "active_customers": int(cur.customer_id.nunique())}


def new_product_share(con, year=CURRENT_YEAR) -> float:
    """Share of revenue from products launched in the last 12 months (Learning & growth view)."""
    return float(pd.read_sql(f"""
        SELECT SUM(CASE WHEN launch_date >= '{year - 1}-01-01' THEN realised_revenue ELSE 0 END)
               / SUM(realised_revenue) r FROM v_sales WHERE year={year}""", con).r[0])


def balanced_scorecard(con, year=CURRENT_YEAR) -> pd.DataFrame:
    a, c = annual_summary(con, year), customer_kpis(con, year)
    actual = {**a, **c, "new_product_rev_share": new_product_share(con, year)}
    rows = [
        ("Financial", "Revenue vs budget", "revenue_vs_budget", "pct"),
        ("Financial", "Gross margin %", "gross_margin_pct", "pct"),
        ("Financial", "Marketing ROI (first-year gross profit per rupee of spend)", "marketing_roi", "x"),
        ("Customer", "Repeat customer rate", "repeat_customer_rate", "pct"),
        ("Customer", "Annual retention", "annual_retention", "pct"),
        ("Internal process", "On-time delivery", "on_time_rate", "pct"),
        ("Internal process", "Return rate (by value)", "return_rate", "pct"),
        ("Learning & growth", "Revenue from new products", "new_product_rev_share", "pct"),
        ("Learning & growth", "New customer growth YoY", "new_customer_growth", "pct"),
    ]
    out = []
    for persp, name, key, unit in rows:
        t = TARGETS[key]
        val = actual[key]
        attain = val / t["target"] if t["direction"] == "higher" else t["target"] / val
        status = "Green" if attain >= 1 else "Amber" if attain >= 0.9 else "Red"
        out.append((persp, name, key, val, t["target"], attain, status, unit))
    return pd.DataFrame(out, columns=["perspective", "kpi", "key", "actual", "target",
                                       "attainment", "status", "unit"])
