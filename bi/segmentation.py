"""Customer analytics: RFM segments, CLV vs CAC by channel, churn decision tree."""
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text

from .config import CURRENT_YEAR, SEED

AS_OF = pd.Timestamp(f"{CURRENT_YEAR}-12-31")
DISCOUNT_RATE = 0.10


def _orders(con):
    df = pd.read_sql("""SELECT customer_id, order_id, MIN(date_key) date_key, SUM(realised_revenue) revenue,
                               SUM(gross_profit) profit, MAX(returned) any_return
                        FROM v_sales GROUP BY customer_id, order_id""", con)
    df["date"] = pd.to_datetime(df.date_key.astype(str))
    return df


def rfm(con, as_of=AS_OF) -> pd.DataFrame:
    o = _orders(con)
    o = o[o.date <= as_of]
    g = o.groupby("customer_id").agg(last=("date", "max"), frequency=("order_id", "nunique"),
                                      monetary=("revenue", "sum"), profit=("profit", "sum"))
    g["recency"] = (as_of - g["last"]).dt.days
    # rank first so ties do not break qcut
    g["R"] = 6 - pd.qcut(g.recency.rank(method="first"), 5, labels=False) - 1
    g["F"] = pd.qcut(g.frequency.rank(method="first"), 5, labels=False) + 1
    g["M"] = pd.qcut(g.monetary.rank(method="first"), 5, labels=False) + 1

    def seg(r):
        if r.R >= 4 and r.F >= 4:
            return "Champions"
        if r.R >= 3 and r.F >= 3:
            return "Loyal"
        if r.F <= 1 and r.R >= 4:
            return "New"
        if r.R <= 2 and r.F >= 3:
            return "At risk"
        if r.R <= 2:
            return "Hibernating"
        return "Promising"
    g["segment"] = g.apply(seg, axis=1)
    return g.reset_index()


def segment_summary(g: pd.DataFrame) -> pd.DataFrame:
    s = g.groupby("segment").agg(customers=("customer_id", "count"), revenue=("monetary", "sum"),
                                 profit=("profit", "sum"), avg_recency=("recency", "mean"),
                                 avg_orders=("frequency", "mean")).reset_index()
    s["customer_share"] = s.customers / s.customers.sum()
    s["revenue_share"] = s.revenue / s.revenue.sum()
    return s.sort_values("revenue", ascending=False).reset_index(drop=True)


def pareto_share(g: pd.DataFrame, top=0.2) -> float:
    r = g.monetary.sort_values(ascending=False)
    return float(r.head(int(len(r) * top)).sum() / r.sum())


def clv_by_channel(con, year=CURRENT_YEAR, discount=DISCOUNT_RATE) -> pd.DataFrame:
    """Simple retention-model CLV: m * r / (1 + i - r), compared with the CAC of the channel."""
    o = pd.read_sql("""SELECT customer_id, channel, year, SUM(gross_profit) profit
                       FROM v_sales GROUP BY customer_id, year""", con)
    prev = o[o.year == year - 1]
    cur = o[o.year == year]
    rows = []
    for ch, p in prev.groupby("channel"):
        kept = p.customer_id.isin(cur.customer_id).mean()
        m = cur[cur.channel == ch].profit.mean()       # annual gross profit per active customer
        clv = m * kept / (1 + discount - kept)
        rows.append((ch, kept, m, clv))
    df = pd.DataFrame(rows, columns=["channel", "retention", "annual_margin", "clv"])
    cac = pd.read_sql(f"SELECT channel, SUM(spend)/SUM(new_customers) cac FROM fact_marketing "
                      f"WHERE ym LIKE '{year}-%' GROUP BY channel", con)
    df = df.merge(cac, on="channel", how="left")
    df["clv_to_cac"] = df.clv / df.cac
    return df


def _features(o: pd.DataFrame, cutoff, tenure_from):
    h = o[o.date <= cutoff]
    f = h.groupby("customer_id").agg(last=("date", "max"), frequency=("order_id", "nunique"),
                                      monetary=("revenue", "sum"), returns=("any_return", "sum"),
                                      first=("date", "min"))
    f["recency"] = (cutoff - f["last"]).dt.days
    f["tenure_days"] = (cutoff - f["first"]).dt.days
    f["avg_order_value"] = f.monetary / f.frequency
    return f[["recency", "frequency", "monetary", "returns", "tenure_days", "avg_order_value"]]


def churn_model(con, cutoff="2025-03-31", horizon_days=180):
    """Depth-3 decision tree: who buys nothing in the 180 days after the cutoff?"""
    o = _orders(con)
    cutoff = pd.Timestamp(cutoff)
    X = _features(o, cutoff, None)
    later = o[(o.date > cutoff) & (o.date <= cutoff + pd.Timedelta(days=horizon_days))].customer_id.unique()
    y = (~X.index.isin(later)).astype(int)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=SEED, stratify=y)
    tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=50, random_state=SEED).fit(Xtr, ytr)
    base = max(yte.mean(), 1 - yte.mean())
    res = {"customers": len(X), "churn_rate": float(y.mean()),
           "accuracy": float(tree.score(Xte, yte)), "baseline_accuracy": float(base),
           "auc": float(roc_auc_score(yte, tree.predict_proba(Xte)[:, 1])),
           "rules": export_text(tree, feature_names=list(X.columns)),
           "importance": dict(zip(X.columns, map(float, tree.feature_importances_)))}
    # Score today's customers with the same model (risk of going quiet in the next 6 months)
    now = _features(o, AS_OF, None)
    risk = pd.Series(tree.predict_proba(now)[:, 1], index=now.index, name="churn_risk")
    return res, risk
