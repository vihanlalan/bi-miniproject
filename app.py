"""Interactive what-if workbench.  Run with:  streamlit run app.py"""
from dataclasses import replace

import pandas as pd
import streamlit as st

from bi import etl, scenario as sc
from bi.config import DB_PATH

st.set_page_config(page_title="ShopSphere what-if workbench", layout="wide")
st.title("ShopSphere: what-if workbench")
st.caption("Simulated data. Move the levers to see the effect on next year's contribution "
           "(gross profit minus marketing). Elasticities are assumptions you can change.")

if not DB_PATH.exists():
    st.error("Warehouse not found. Run `python -m bi.pipeline` first.")
    st.stop()


@st.cache_data
def load_baseline():
    con = etl.connect()
    try:
        return sc.baseline_from_db(con)
    finally:
        con.close()


b = load_baseline()
base = sc.project(b)

with st.sidebar:
    st.header("Levers")
    price = st.slider("List price change (%)", -15, 15, 0) / 100
    disc = st.slider("Discount change (points)", -5, 8, 0) / 100
    mkt = st.slider("Marketing spend change (%)", -50, 100, 0) / 100
    ret = st.slider("Return rate change (points)", -5, 5, 0) / 100
    cost = st.slider("Supplier cost change (%)", -10, 15, 0) / 100
    st.header("Assumptions")
    elas = st.slider("Price elasticity of demand", -3.0, -0.5, -1.3, 0.1)
    expo = st.slider("Marketing diminishing-returns exponent", 0.2, 1.0, 0.6, 0.05)

lev = sc.Levers(price, disc, mkt, ret, cost, elas, expo)
res = sc.project(b, lev)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue (Rs M)", f"{res['revenue'] / 1e6:.1f}", f"{res['revenue'] / base['revenue'] - 1:+.1%}")
c2.metric("Gross profit (Rs M)", f"{res['gross_profit'] / 1e6:.1f}", f"{res['gross_profit'] / base['gross_profit'] - 1:+.1%}")
c3.metric("Marketing (Rs M)", f"{res['marketing'] / 1e6:.2f}", f"{res['marketing'] / base['marketing'] - 1:+.1%}")
c4.metric("Contribution (Rs M)", f"{res['contribution'] / 1e6:.2f}", f"{res['contribution'] / base['contribution'] - 1:+.1%}")

st.subheader("Goal seek")
target_pct = st.slider("Contribution target (% above baseline)", 1, 30, 10)
p = sc.goal_seek_price(b, base["contribution"] * (1 + target_pct / 100), replace(lev, price_change=0.0))
st.write(f"List price change needed (other levers as set above): **{p:+.1%}**" if p is not None
         else "Not reachable with a price change between -20% and +30%.")

st.subheader("Risk: Monte Carlo on this plan")
if st.button("Run 5,000 simulations"):
    mc = sc.monte_carlo(b, lev, n=5000)
    st.write(f"Mean Rs {mc['mean'] / 1e6:.2f}M, 5th percentile Rs {mc['p5'] / 1e6:.2f}M, "
             f"chance of ending below baseline {mc['prob_below_baseline']:.0%}.")
    st.bar_chart(pd.Series(mc["samples"] / 1e6).round(1).value_counts().sort_index())
