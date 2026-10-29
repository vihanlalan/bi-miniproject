"""Static matplotlib figures (used in the PDF report)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import FIG_DIR

C = {"blue": "#2a6f97", "orange": "#e07a1f", "grey": "#8a8f98", "red": "#c0392b",
     "green": "#2e8b57", "amber": "#d4a017", "light": "#cfd8e3"}
RAG = {"Green": C["green"], "Amber": C["amber"], "Red": C["red"]}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "figure.dpi": 150})


def _save(fig, name):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG_DIR / f"{name}.png")
    plt.close(fig)


def revenue_vs_budget(R):
    m = R["monthly"]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    x = np.arange(len(m))
    ax.bar(x, m.revenue / 1e6, color=C["blue"], label="Actual revenue")
    ax.plot(x, m.revenue_budget / 1e6, color=C["orange"], marker="o", ms=3, label="Budget")
    ax.set_xticks(x[::2]); ax.set_xticklabels(m.ym[::2], rotation=45, ha="right")
    ax.set_ylabel("Rs million"); ax.set_title("Monthly revenue against budget"); ax.legend(frameon=False)
    _save(fig, "revenue_vs_budget")


def margin_trend(R):
    m = R["monthly"]
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.plot(m.ym, m.gross_margin_pct * 100, color=C["blue"], marker="o", ms=3)
    ax.axhline(28, color=C["orange"], ls="--", lw=1, label="Target 28%")
    promo = m.ym.str[-2:].isin(["06", "11", "12"])
    ax.scatter(m.ym[promo], m.gross_margin_pct[promo] * 100, color=C["red"], zorder=3, label="Promo month")
    ax.set_xticks(range(0, len(m), 2)); ax.set_xticklabels(m.ym[::2], rotation=45, ha="right")
    ax.set_ylabel("Gross margin %"); ax.set_title("Gross margin by month"); ax.legend(frameon=False)
    _save(fig, "margin_trend")


def scorecard(R):
    s = R["scorecard"]
    fig, ax = plt.subplots(figsize=(7, 3.4))
    y = np.arange(len(s))[::-1]
    ax.barh(y, s.attainment.clip(upper=1.6) * 100, color=[RAG[x] for x in s.status])
    ax.axvline(100, color="black", lw=1)
    ax.set_yticks(y); ax.set_yticklabels(s.kpi.str.replace(r" \(.*\)", "", regex=True))
    ax.set_xlabel("Attainment against target (%, capped at 160)"); ax.set_title("Balanced scorecard, FY2025")
    _save(fig, "scorecard")


def channels(R):
    ch = R["channels"].sort_values("cac")
    cm = R["channel_monthly"]
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3))
    axs[0].bar(ch.channel, ch.cac, color=C["blue"])
    axs[0].set_title("CAC by channel, FY2025"); axs[0].set_ylabel("Rs per new customer")
    for ch_name, g in cm.groupby("channel"):
        axs[1].plot(g.ym, g.cac, label=ch_name, lw=2 if ch_name == "Social" else 1,
                    color=C["red"] if ch_name == "Social" else None)
    axs[1].set_xticks(range(0, 24, 4)); axs[1].set_xticklabels(sorted(cm.ym.unique())[::4], rotation=45, ha="right")
    axs[1].set_title("Monthly CAC"); axs[1].legend(frameon=False, fontsize=7)
    _save(fig, "channels")


def segments(R):
    s = R["segments"]
    fig, ax = plt.subplots(figsize=(7, 3))
    x = np.arange(len(s)); w = 0.38
    ax.bar(x - w / 2, s.customer_share * 100, w, label="Share of customers", color=C["light"])
    ax.bar(x + w / 2, s.revenue_share * 100, w, label="Share of revenue", color=C["blue"])
    ax.set_xticks(x); ax.set_xticklabels(s.segment); ax.set_ylabel("%")
    ax.set_title("RFM segments"); ax.legend(frameon=False)
    _save(fig, "segments")


def tornado(R):
    t = R["tornado"].iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 3))
    y = np.arange(len(t))
    ax.barh(y, t.upside / 1e6, color=C["green"], label="Favourable move")
    ax.barh(y, t.downside / 1e6, color=C["red"], label="Adverse move")
    ax.set_yticks(y); ax.set_yticklabels(t.driver); ax.axvline(0, color="black", lw=1)
    ax.set_xlabel("Change in annual contribution (Rs million)")
    ax.set_title("Sensitivity of contribution"); ax.legend(frameon=False, loc="lower right")
    _save(fig, "tornado")


def monte_carlo(R):
    mc = R["mc"]
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.hist(mc["samples"] / 1e6, bins=50, color=C["light"], edgecolor="white")
    for key, col, lab in [("p5", C["red"], "5th percentile"), ("p95", C["green"], "95th percentile"),
                          ("baseline", C["orange"], "Do-nothing baseline")]:
        ax.axvline(mc[key] / 1e6, color=col, lw=1.5, label=f"{lab}: {mc[key] / 1e6:.1f}")
    ax.set_xlabel("Annual contribution (Rs million)"); ax.set_ylabel("Simulations")
    ax.set_title("Monte Carlo: combined plan, 10,000 runs"); ax.legend(frameon=False, fontsize=8)
    _save(fig, "monte_carlo")


def vendors(R):
    v = R["vendor_rank"].iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.barh(v.vendor_name, v.topsis, color=C["blue"])
    for i, (t, ot) in enumerate(zip(v.topsis, v.on_time_rate)):
        ax.text(t + 0.01, i, f"{t:.2f}  (on-time {ot:.0%})", va="center", fontsize=8)
    ax.set_xlim(0, 1.15); ax.set_title("Vendor ranking by TOPSIS closeness score")
    _save(fig, "vendors")


def save_all(R):
    for fn in (revenue_vs_budget, margin_trend, scorecard, channels, segments, tornado, monte_carlo, vendors):
        fn(R)
