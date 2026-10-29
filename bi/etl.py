"""ETL: raw CSVs -> cleaned star schema in SQLite, with a data quality report."""
import sqlite3

import numpy as np
import pandas as pd

from .config import DB_PATH, RAW_DIR, RETURN_HANDLING_RATE

SCHEMA_VIEWS = """
DROP VIEW IF EXISTS v_sales;
CREATE VIEW v_sales AS
SELECT f.*, d.ym, d.year, d.quarter, d.month, p.category, p.vendor_id, p.launch_date,
       v.vendor_name, c.channel, c.region, c.signup_date
FROM fact_sales f
JOIN dim_date d ON d.date_key = f.date_key
JOIN dim_product p ON p.product_id = f.product_id
JOIN dim_vendor v ON v.vendor_id = p.vendor_id
JOIN dim_customer c ON c.customer_id = f.customer_id;
"""


def clean_sales(raw: pd.DataFrame, valid_customers, valid_products):
    """Apply cleaning rules and return (clean_df, dq_log)."""
    log = {"raw_rows": len(raw)}
    df = raw.copy()
    df["order_date"] = pd.to_datetime(df.order_date)

    dup = df.duplicated("line_id", keep="first")
    log["duplicate_lines_removed"] = int(dup.sum())
    df = df[~dup]

    neg = df.qty <= 0
    log["negative_qty_removed"] = int(neg.sum())
    df = df[~neg]

    orphan = ~df.customer_id.isin(valid_customers) | ~df.product_id.isin(valid_products)
    log["orphan_rows_removed"] = int(orphan.sum())
    df = df[~orphan]

    log["null_delivery_days_imputed"] = int(df.delivery_days.isna().sum())
    # impute with the median delivery time of the same product (a simple, explainable rule)
    med = df.groupby("product_id").delivery_days.transform("median")
    df["delivery_days"] = df.delivery_days.fillna(med).round().astype(int)

    log["clean_rows"] = len(df)
    return df.reset_index(drop=True), log


def build_warehouse(raw_dir=RAW_DIR, db_path=DB_PATH):
    raw = {n: pd.read_csv(raw_dir / f"{n}.csv") for n in
           ["vendors", "products", "customers", "sales", "marketing", "budget"]}
    vendors, products = raw["vendors"], raw["products"]
    customers = raw["customers"].assign(signup_date=lambda d: pd.to_datetime(d.signup_date))

    sales, dq = clean_sales(raw["sales"], set(customers.customer_id), set(products.product_id))

    # fact_sales: derived measures are calculated once, here, so every report uses the same maths
    sales = sales.merge(products[["product_id", "unit_cost"]], on="product_id")
    sales["gross_sales"] = (sales.qty * sales.unit_price).round(2)
    sales["discount_amt"] = (sales.gross_sales * sales.discount_rate).round(2)
    sales["net_revenue"] = sales.gross_sales - sales.discount_amt
    sales["cogs"] = (sales.qty * sales.unit_cost).round(2)
    keep = 1 - sales.returned
    sales["realised_revenue"] = (sales.net_revenue * keep).round(2)
    sales["realised_cogs"] = (sales.cogs * keep).round(2)
    sales["return_cost"] = (sales.net_revenue * sales.returned * RETURN_HANDLING_RATE).round(2)
    sales["gross_profit"] = sales.realised_revenue - sales.realised_cogs - sales.return_cost
    sales["on_time"] = (sales.delivery_days <= sales.promised_days).astype(int)
    sales["date_key"] = sales.order_date.dt.strftime("%Y%m%d").astype(int)
    fact_cols = ["line_id", "order_id", "date_key", "customer_id", "product_id", "qty", "unit_price",
                 "discount_rate", "gross_sales", "discount_amt", "net_revenue", "cogs", "returned",
                 "realised_revenue", "realised_cogs", "return_cost", "gross_profit",
                 "promised_days", "delivery_days", "on_time"]
    fact = sales[fact_cols]

    dates = pd.DataFrame({"date": pd.date_range("2024-01-01", "2025-12-31")})
    dates["date_key"] = dates.date.dt.strftime("%Y%m%d").astype(int)
    dates["year"], dates["quarter"], dates["month"] = dates.date.dt.year, dates.date.dt.quarter, dates.date.dt.month
    dates["ym"] = dates.date.dt.strftime("%Y-%m")
    dates["is_promo_month"] = dates.month.isin([6, 11, 12]).astype(int)
    dates["date"] = dates.date.dt.strftime("%Y-%m-%d")

    customers["signup_date"] = customers.signup_date.dt.strftime("%Y-%m-%d")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    for name, df in {"dim_date": dates, "dim_customer": customers, "dim_product": products,
                     "dim_vendor": vendors, "fact_sales": fact,
                     "fact_marketing": raw["marketing"], "fact_budget": raw["budget"]}.items():
        df.to_sql(name, con, index=False)
    con.executescript(SCHEMA_VIEWS)
    con.executescript("CREATE INDEX ix_fs_date ON fact_sales(date_key);"
                      "CREATE INDEX ix_fs_cust ON fact_sales(customer_id);")
    dq.update(quality_checks(con))
    con.commit()
    con.close()
    return dq


def quality_checks(con):
    """Post-load checks. Every value should be zero."""
    q = {
        "null_keys": "SELECT COUNT(*) FROM fact_sales WHERE customer_id IS NULL OR product_id IS NULL OR date_key IS NULL",
        "duplicate_line_ids": "SELECT COUNT(*) - COUNT(DISTINCT line_id) FROM fact_sales",
        "orphan_customers": "SELECT COUNT(*) FROM fact_sales WHERE customer_id NOT IN (SELECT customer_id FROM dim_customer)",
        "orders_before_signup": "SELECT COUNT(*) FROM v_sales WHERE date(substr(date_key,1,4)||'-'||substr(date_key,5,2)||'-'||substr(date_key,7,2)) < date(signup_date)",
        "negative_revenue": "SELECT COUNT(*) FROM fact_sales WHERE net_revenue < 0",
    }
    return {f"check_{k}": con.execute(s).fetchone()[0] for k, s in q.items()}


def connect(db_path=DB_PATH):
    return sqlite3.connect(db_path)


if __name__ == "__main__":
    print(build_warehouse())
