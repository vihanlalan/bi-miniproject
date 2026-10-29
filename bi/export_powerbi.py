"""Export the star schema and analytics results as one Excel workbook for Power BI.

    python -m bi.export_powerbi        ->  powerbi/ShopSphere_BI_Data.xlsx

One sheet per table. In Power BI Desktop: Get data > Excel workbook > select all sheets > Load.
"""
import numpy as np
import pandas as pd

from . import etl, pipeline
from .config import ROOT

OUT = ROOT / "powerbi" / "ShopSphere_BI_Data.xlsx"


def build_tables(con, R):
    t = {}
    d = pd.read_sql("SELECT * FROM dim_date", con)
    d["date"] = pd.to_datetime(d.date)
    t["dim_date"] = d
    mon = d.groupby("ym").agg(month_start=("date", "min"), year=("year", "first"), month=("month", "first")).reset_index()
    mon["month_label"] = mon.month_start.dt.strftime("%b %Y")
    mon["fiscal_year"] = "FY" + mon.year.astype(str)
    t["dim_month"] = mon

    c = pd.read_sql("SELECT * FROM dim_customer", con)
    c["signup_date"] = pd.to_datetime(c.signup_date)
    c["signup_year"] = c.signup_date.dt.year
    rfm = R["rfm"][["customer_id", "recency", "frequency", "monetary", "R", "F", "M", "segment"]]
    c = c.merge(rfm, on="customer_id", how="left").merge(
        R["churn_risk"].reset_index(), on="customer_id", how="left")
    c["segment"] = c.segment.fillna("No purchases")
    c["churn_risk_band"] = pd.cut(c.churn_risk, [-0.01, 0.4, 0.7, 1.0], labels=["Low", "Medium", "High"]).astype(str)
    t["dim_customer"] = c.rename(columns={"recency": "recency_days", "frequency": "orders_total",
                                          "monetary": "lifetime_revenue", "R": "rfm_r", "F": "rfm_f", "M": "rfm_m"})
    t["dim_channel"] = pd.DataFrame({"channel": ["Search", "Social", "Email", "Affiliate", "Organic"]})
    t["dim_product"] = pd.read_sql("SELECT * FROM dim_product", con).assign(
        launch_date=lambda x: pd.to_datetime(x.launch_date))

    v = pd.read_sql("SELECT * FROM dim_vendor", con).merge(
        R["vendor_rank"][["vendor_id", "topsis", "weighted_sum", "topsis_rank", "wsm_rank"]], on="vendor_id")
    st = R["vendor_stability"].rename(columns={"vendor_name": "vendor_name"})
    t["dim_vendor"] = v.merge(st, on="vendor_name")

    t["fact_sales"] = pd.read_sql("SELECT * FROM fact_sales", con)
    t["fact_marketing"] = pd.read_sql("SELECT * FROM fact_marketing", con)
    t["fact_budget"] = pd.read_sql("SELECT * FROM fact_budget", con)

    # results that come from Python models (too heavy or not meaningful in DAX)
    sc = R["scorecard"].copy()
    sc["sort"] = range(1, len(sc) + 1)
    t["scorecard"] = sc
    t["alerts"] = R["alerts"]
    t["scenarios"] = R["scenarios"]
    t["tornado"] = R["tornado"]
    t["clv_by_channel"] = R["clv"]
    t["categories"] = R["categories"]

    samples = R["mc"]["samples"] / 1e6
    counts, edges = np.histogram(samples, bins=40)
    t["monte_carlo_hist"] = pd.DataFrame({"contribution_rs_million": ((edges[:-1] + edges[1:]) / 2).round(3), "runs": counts})
    mc = R["mc"]
    t["monte_carlo_summary"] = pd.DataFrame({"stat": ["Baseline", "Mean", "P5", "Median", "P95", "Prob below baseline"],
                                             "value": [mc["baseline"], mc["mean"], mc["p5"], mc["p50"], mc["p95"],
                                                       mc["prob_below_baseline"]]})
    return t


def main():
    con = etl.connect()
    R = pipeline.compute(con)
    t = build_tables(con, R)
    con.close()
    OUT.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUT, engine="xlsxwriter", datetime_format="yyyy-mm-dd") as xw:
        for name, df in t.items():
            df.to_excel(xw, sheet_name=name, index=False)
    print("wrote", OUT, {k: len(v) for k, v in t.items()})
    return t, R


if __name__ == "__main__":
    main()
