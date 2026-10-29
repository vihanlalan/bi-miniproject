"""Tests build a small warehouse once (module scope) and check the maths and the data rules."""
import numpy as np
import pandas as pd
import pytest

from bi import alerts, etl, kpi, mcdm, scenario as sc, segmentation as sg, generate_data
from bi.config import CURRENT_YEAR


_DQ = {}


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    d = tmp_path_factory.mktemp("bi")
    generate_data.generate(d / "raw")
    dq = etl.build_warehouse(d / "raw", d / "w.db")
    c = etl.connect(d / "w.db")
    _DQ.update(dq)
    return c


def test_etl_cleaning_counts(con):
    assert _DQ["duplicate_lines_removed"] == 45
    assert _DQ["negative_qty_removed"] == 12
    assert _DQ["null_delivery_days_imputed"] == 70
    assert all(v == 0 for k, v in _DQ.items() if k.startswith("check_"))


def test_revenue_ties_between_views(con):
    m = kpi.monthly(con)
    total = con.execute("SELECT SUM(realised_revenue) FROM fact_sales").fetchone()[0]
    assert m.revenue.sum() == pytest.approx(total)
    a = kpi.annual_summary(con)
    assert a["revenue"] == pytest.approx(m[m.ym.str.startswith(str(CURRENT_YEAR))].revenue.sum())


def test_profit_identity(con):
    r = con.execute("SELECT SUM(realised_revenue - realised_cogs - return_cost - gross_profit) FROM fact_sales").fetchone()[0]
    assert abs(r) < 1.0


def test_scorecard_status_logic(con):
    s = kpi.balanced_scorecard(con)
    assert set(s.status) <= {"Green", "Amber", "Red"}
    greens = s[s.status == "Green"]
    assert (greens.attainment >= 1).all()


def test_rfm_covers_every_buyer_once(con):
    g = sg.rfm(con)
    n = con.execute("SELECT COUNT(DISTINCT customer_id) FROM fact_sales").fetchone()[0]
    assert len(g) == n and g.customer_id.is_unique
    assert g[["R", "F", "M"]].min().min() >= 1 and g[["R", "F", "M"]].max().max() <= 5


def test_churn_tree_beats_majority_class(con):
    res, risk = sg.churn_model(con)
    assert res["accuracy"] > res["baseline_accuracy"]
    assert risk.between(0, 1).all()


def test_scenario_baseline_matches_actuals(con):
    b = sc.baseline_from_db(con)
    actual = kpi.annual_summary(con)["contribution"]
    assert sc.project(b)["contribution"] == pytest.approx(actual, rel=0.01)


def test_scenario_directions(con):
    b = sc.baseline_from_db(con)
    base = sc.project(b)["contribution"]
    assert sc.project(b, sc.Levers(cogs_change=0.05))["contribution"] < base
    assert sc.project(b, sc.Levers(return_rate_change=-0.02))["contribution"] > base
    assert sc.project(b, sc.Levers(price_change=0.03))["revenue"] < sc.project(b)["revenue"]  # elastic demand


def test_goal_seek_hits_target(con):
    b = sc.baseline_from_db(con)
    target = sc.project(b)["contribution"] * 1.05
    p = sc.goal_seek_price(b, target)
    assert p is not None
    assert sc.project(b, sc.Levers(price_change=p))["contribution"] == pytest.approx(target, rel=1e-6)


def test_monte_carlo_reproducible(con):
    b = sc.baseline_from_db(con)
    plan = sc.Levers(price_change=0.02)
    a = sc.monte_carlo(b, plan, n=500)
    c = sc.monte_carlo(b, plan, n=500)
    assert a["mean"] == c["mean"] and a["p5"] < a["p50"] < a["p95"]


def test_topsis_dominant_vendor_wins():
    df = pd.DataFrame({"vendor_name": ["good", "bad"], "cost_index": [0.8, 1.2], "on_time_rate": [0.99, 0.6],
                       "return_rate": [0.05, 0.15], "avg_delivery_days": [3, 6]})
    s = mcdm.topsis(df)
    assert s.iloc[0] > s.iloc[1]
    assert 0 <= s.min() and s.max() <= 1


def test_alerts_find_injected_problems(con):
    a = alerts.generate(con)
    txt = " ".join(a.message)
    assert "Evergreen" in txt and "Social CAC" in txt
