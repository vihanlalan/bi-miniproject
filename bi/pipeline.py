"""End-to-end run: generate -> ETL -> analytics -> dashboard, figures and results.json.

    python -m bi.pipeline
"""
import json

import pandas as pd

from . import alerts, charts, dashboard, etl, generate_data, kpi, mcdm, scenario, segmentation
from .config import CURRENT_YEAR, DB_PATH, OUT_DIR, RAW_DIR

PLAN = scenario.DEFAULT_SCENARIOS["Combined: price +2%, marketing +10%, returns -2 pts"]


def compute(con) -> dict:
    """Run every analytic once and return the objects the dashboard, charts and report share."""
    R = {}
    R["monthly"] = kpi.monthly(con)
    R["annual"] = kpi.annual_summary(con)
    R["customer_kpis"] = kpi.customer_kpis(con)
    R["scorecard"] = kpi.balanced_scorecard(con)
    R["channels"] = kpi.channel_performance(con)
    R["channel_monthly"] = kpi.channel_monthly(con)
    R["categories"] = kpi.category_performance(con)
    R["vendors"] = kpi.vendor_performance(con)
    R["vendor_monthly"] = kpi.vendor_monthly_on_time(con)
    R["alerts"] = alerts.generate(con)

    rfm = segmentation.rfm(con)
    R["rfm"] = rfm
    R["segments"] = segmentation.segment_summary(rfm)
    R["pareto_top20"] = segmentation.pareto_share(rfm)
    R["clv"] = segmentation.clv_by_channel(con)
    R["churn"], R["churn_risk"] = segmentation.churn_model(con)
    risk = rfm.merge(R["churn_risk"].reset_index(), on="customer_id")
    R["high_risk_revenue"] = float(risk[risk.churn_risk >= 0.7].monetary.sum())
    R["high_risk_customers"] = int((risk.churn_risk >= 0.7).sum())

    b = scenario.baseline_from_db(con)
    R["baseline"] = b
    R["scenarios"] = scenario.compare(b, scenario.DEFAULT_SCENARIOS)
    R["tornado"] = scenario.tornado(b)
    R["breakeven_elasticity"] = scenario.breakeven_elasticity(b)
    base_c = scenario.project(b)["contribution"]
    R["goal_target"] = base_c * 1.10
    R["goal_price"] = scenario.goal_seek_price(b, R["goal_target"])
    R["mc"] = scenario.monte_carlo(b, PLAN)
    R["mc_plan"] = PLAN

    R["vendor_rank"] = mcdm.rank_vendors(R["vendors"])
    R["vendor_stability"] = mcdm.rank_stability(R["vendors"])
    return R


def summary(R: dict, dq: dict) -> dict:
    """Plain numbers for results.json (the report reads these)."""
    mc = {k: v for k, v in R["mc"].items() if k != "samples"}
    f = lambda d: {k: (float(v) if isinstance(v, (int, float)) or hasattr(v, "item") else v) for k, v in d.items()}
    return {
        "data_quality": dq,
        "annual": f(R["annual"]),
        "customer_kpis": f(R["customer_kpis"]),
        "scorecard": R["scorecard"].drop(columns="unit").to_dict("records"),
        "channels": R["channels"].to_dict("records"),
        "clv": R["clv"].to_dict("records"),
        "segments": R["segments"].to_dict("records"),
        "pareto_top20": R["pareto_top20"],
        "churn": {k: v for k, v in R["churn"].items()},
        "high_risk_customers": R["high_risk_customers"], "high_risk_revenue": R["high_risk_revenue"],
        "scenarios": R["scenarios"].to_dict("records"),
        "tornado": R["tornado"].to_dict("records"),
        "breakeven_elasticity": R["breakeven_elasticity"],
        "goal_target": R["goal_target"], "goal_price": R["goal_price"],
        "monte_carlo": mc,
        "vendor_rank": R["vendor_rank"].to_dict("records"),
        "vendor_stability": R["vendor_stability"].to_dict("records"),
        "alerts": R["alerts"].to_dict("records"),
        "categories": R["categories"].to_dict("records"),
        "monthly": R["monthly"].to_dict("records"),
    }


def main(regenerate=True):
    if regenerate or not (RAW_DIR / "sales.csv").exists():
        print("1/4 generating synthetic data ...", generate_data.generate())
    dq = etl.build_warehouse()
    print("2/4 ETL done:", {k: v for k, v in dq.items() if not k.startswith("check_")})
    con = etl.connect(DB_PATH)
    R = compute(con)
    con.close()
    OUT_DIR.mkdir(exist_ok=True)
    print("3/4 analytics done")
    for name in ["monthly", "scorecard", "channels", "clv", "segments", "scenarios", "tornado",
                 "vendor_rank", "alerts", "categories"]:
        R[name].to_csv(OUT_DIR / f"{name}.csv", index=False)
    charts.save_all(R)
    dashboard.build(R, OUT_DIR / "dashboard.html")
    (OUT_DIR / "results.json").write_text(json.dumps(summary(R, dq), indent=2, default=str))
    print("4/4 wrote outputs/dashboard.html, outputs/results.json and outputs/figures/")
    return R


if __name__ == "__main__":
    main()
