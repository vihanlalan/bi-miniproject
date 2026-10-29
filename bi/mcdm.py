"""Multi-criteria decision making: vendor ranking with weighted sum and TOPSIS."""
import numpy as np
import pandas as pd

from .config import SEED

# (column, direction) where direction is +1 if higher is better, -1 if lower is better
CRITERIA = {
    "cost_index": -1,
    "on_time_rate": +1,
    "return_rate": -1,
    "avg_delivery_days": -1,
}
DEFAULT_WEIGHTS = {"cost_index": 0.30, "on_time_rate": 0.30, "return_rate": 0.25, "avg_delivery_days": 0.15}


def topsis(df: pd.DataFrame, weights: dict = DEFAULT_WEIGHTS) -> pd.Series:
    X = df[list(CRITERIA)].to_numpy(float)
    w = np.array([weights[c] for c in CRITERIA], float)
    w = w / w.sum()
    V = X / np.linalg.norm(X, axis=0) * w
    sign = np.array(list(CRITERIA.values()))
    best = np.where(sign > 0, V.max(axis=0), V.min(axis=0))
    worst = np.where(sign > 0, V.min(axis=0), V.max(axis=0))
    d_best = np.linalg.norm(V - best, axis=1)
    d_worst = np.linalg.norm(V - worst, axis=1)
    return pd.Series(d_worst / (d_best + d_worst), index=df.index)


def weighted_sum(df: pd.DataFrame, weights: dict = DEFAULT_WEIGHTS) -> pd.Series:
    score = pd.Series(0.0, index=df.index)
    for c, s in CRITERIA.items():
        x = df[c]
        norm = (x - x.min()) / (x.max() - x.min())
        score += weights[c] * (norm if s > 0 else 1 - norm)
    return score / sum(weights.values())


def rank_vendors(vendors: pd.DataFrame, weights: dict = DEFAULT_WEIGHTS) -> pd.DataFrame:
    df = vendors.copy()
    df["topsis"] = topsis(df, weights)
    df["weighted_sum"] = weighted_sum(df, weights)
    df["topsis_rank"] = df.topsis.rank(ascending=False).astype(int)
    df["wsm_rank"] = df.weighted_sum.rank(ascending=False).astype(int)
    return df.sort_values("topsis_rank").reset_index(drop=True)


def rank_stability(vendors: pd.DataFrame, n=5000, seed=SEED) -> pd.DataFrame:
    """How often each vendor ranks first when the weights are drawn at random."""
    rng = np.random.default_rng(seed)
    wins = pd.Series(0, index=vendors.vendor_name)
    for w in rng.dirichlet(np.ones(len(CRITERIA)), size=n):
        s = topsis(vendors, dict(zip(CRITERIA, w)))
        wins[vendors.vendor_name.iloc[int(np.argmax(s.to_numpy()))]] += 1
    return (wins / n).rename("share_ranked_first").reset_index().sort_values(
        "share_ranked_first", ascending=False).reset_index(drop=True)
