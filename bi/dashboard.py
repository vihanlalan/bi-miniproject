"""Executive dashboard: one self-contained HTML page built with Plotly (loaded from a CDN)."""
import plotly.graph_objects as go
from jinja2 import Template

PLOTLY_CDN = "https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js"
BLUE, ORANGE, RED, GREEN, AMBER, GREY = "#2a6f97", "#e07a1f", "#c0392b", "#2e8b57", "#d4a017", "#cfd8e3"
RAG = {"Green": GREEN, "Amber": AMBER, "Red": RED}
LAYOUT = dict(margin=dict(l=50, r=20, t=40, b=40), height=320, font=dict(size=12),
              paper_bgcolor="white", plot_bgcolor="white", legend=dict(orientation="h", y=-0.25))


def _div(fig, title):
    fig.update_layout(title=dict(text=title, x=0), **LAYOUT)
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False})


def _fmt_money(x):
    return f"Rs {x / 1e7:.2f} Cr" if abs(x) >= 1e7 else f"Rs {x / 1e5:.1f} L"


def build(R: dict, path):
    m, a = R["monthly"], R["annual"]
    figs = []

    f = go.Figure([go.Bar(x=m.ym, y=m.revenue, name="Actual", marker_color=BLUE),
                   go.Scatter(x=m.ym, y=m.revenue_budget, name="Budget", mode="lines+markers",
                              line=dict(color=ORANGE))])
    figs.append(_div(f, "Revenue against budget"))

    f = go.Figure([go.Scatter(x=m.ym, y=m.gross_margin_pct * 100, mode="lines+markers", name="Gross margin %",
                              line=dict(color=BLUE)),
                   go.Scatter(x=m.ym, y=[28] * len(m), name="Target 28%", line=dict(color=ORANGE, dash="dash"))])
    f.update_yaxes(title="%")
    figs.append(_div(f, "Gross margin: promo months (Jun, Nov, Dec) dip"))

    s = R["scorecard"]
    f = go.Figure(go.Bar(y=s.kpi.str.replace(r" \(.*\)", "", regex=True)[::-1], x=(s.attainment * 100)[::-1],
                         orientation="h", marker_color=[RAG[x] for x in s.status[::-1]],
                         text=[f"{x:.0f}%" for x in (s.attainment * 100)[::-1]], textposition="outside"))
    f.add_vline(x=100, line_color="black")
    f.update_layout(xaxis_range=[0, 190])
    figs.append(_div(f, "Balanced scorecard: attainment vs target"))

    cm = R["channel_monthly"]
    f = go.Figure([go.Scatter(x=g.ym, y=g.cac, name=c, mode="lines",
                              line=dict(width=4 if c == "Social" else 1.5)) for c, g in cm.groupby("channel")])
    f.update_yaxes(title="Rs per new customer")
    figs.append(_div(f, "Customer acquisition cost by channel"))

    seg = R["segments"]
    f = go.Figure([go.Bar(x=seg.segment, y=seg.customer_share * 100, name="% of customers", marker_color=GREY),
                   go.Bar(x=seg.segment, y=seg.revenue_share * 100, name="% of revenue", marker_color=BLUE)])
    f.update_layout(barmode="group")
    figs.append(_div(f, "RFM segments: who brings the revenue"))

    v = R["vendor_rank"]
    f = go.Figure(go.Bar(y=v.vendor_name[::-1], x=v.topsis[::-1], orientation="h", marker_color=BLUE,
                         text=[f"on-time {x:.0%}" for x in v.on_time_rate[::-1]], textposition="outside"))
    f.update_xaxes(range=[0, 1.1])
    figs.append(_div(f, "Vendor ranking (TOPSIS score)"))

    t = R["tornado"].iloc[::-1]
    f = go.Figure([go.Bar(y=t.driver, x=t.upside / 1e6, orientation="h", name="Favourable", marker_color=GREEN),
                   go.Bar(y=t.driver, x=t.downside / 1e6, orientation="h", name="Adverse", marker_color=RED)])
    f.update_layout(barmode="overlay")
    f.update_xaxes(title="Change in contribution (Rs million)")
    figs.append(_div(f, "What moves profit most (sensitivity)"))

    mc = R["mc"]
    f = go.Figure(go.Histogram(x=mc["samples"] / 1e6, nbinsx=50, marker_color=GREY))
    f.add_vline(x=mc["baseline"] / 1e6, line_color=ORANGE, annotation_text="do nothing")
    f.add_vline(x=mc["p5"] / 1e6, line_color=RED, annotation_text="P5")
    f.update_xaxes(title="Contribution (Rs million)")
    figs.append(_div(f, "Monte Carlo: combined plan"))

    tiles = [
        ("Revenue FY2025", _fmt_money(a["revenue"]), f"{a['yoy_growth']:+.0%} YoY"),
        ("vs budget", f"{a['revenue_vs_budget']:.0%}", "of plan"),
        ("Gross margin", f"{a['gross_margin_pct']:.1%}", "target 28%"),
        ("Contribution", _fmt_money(a["contribution"]), "after marketing"),
        ("On-time delivery", f"{a['on_time_rate']:.1%}", "target 85%"),
        ("Return rate", f"{a['return_rate']:.1%}", "target 8%"),
    ]
    html = Template(TEMPLATE).render(tiles=tiles, figs=figs, alerts=R["alerts"].to_dict("records"),
                                     score=s.to_dict("records"), cdn=PLOTLY_CDN, rag=RAG)
    path.write_text(html, encoding="utf-8")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ShopSphere strategic BI dashboard</title>
<script src="{{ cdn }}"></script>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f3f5f8;color:#1f2933}
 header{background:#1d3557;color:#fff;padding:16px 28px}
 header h1{margin:0;font-size:22px} header p{margin:4px 0 0;font-size:13px;opacity:.8}
 main{padding:20px 28px;max-width:1300px;margin:auto}
 .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:18px}
 .tile{background:#fff;border-radius:8px;padding:12px 14px;box-shadow:0 1px 3px #0001}
 .tile .v{font-size:24px;font-weight:600} .tile .l{font-size:12px;color:#52606d} .tile .s{font-size:12px;color:#52606d}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:14px}
 .card{background:#fff;border-radius:8px;padding:6px;box-shadow:0 1px 3px #0001;overflow:hidden}
 table{border-collapse:collapse;width:100%;font-size:13px} th,td{padding:6px 8px;border-bottom:1px solid #e4e7eb;text-align:left}
 .pill{display:inline-block;padding:1px 8px;border-radius:10px;color:#fff;font-size:12px}
 h2{font-size:16px;margin:22px 0 8px}
</style></head><body>
<header><h1>ShopSphere: strategic BI dashboard</h1>
<p>FY2025 view for the executive team. All data is simulated for a course mini project.</p></header>
<main>
<div class="tiles">{% for l,v,s in tiles %}<div class="tile"><div class="l">{{l}}</div><div class="v">{{v}}</div><div class="s">{{s}}</div></div>{% endfor %}</div>

<h2>Exceptions needing attention</h2>
<div class="card"><table><tr><th>Month</th><th>Severity</th><th>Area</th><th>Alert</th></tr>
{% for a in alerts %}<tr><td>{{a.month}}</td>
<td><span class="pill" style="background:{{ {'High':'#c0392b','Medium':'#d4a017','Low':'#8a8f98'}[a.severity] }}">{{a.severity}}</span></td>
<td>{{a.area}}</td><td>{{a.message}}</td></tr>{% endfor %}</table></div>

<h2>Balanced scorecard</h2>
<div class="card"><table><tr><th>Perspective</th><th>KPI</th><th>Actual</th><th>Target</th><th>Status</th></tr>
{% for r in score %}<tr><td>{{r.perspective}}</td><td>{{r.kpi}}</td>
<td>{{ ('%.2f' % r.actual) if r.unit=='x' else ('%.1f%%' % (r.actual*100)) }}</td>
<td>{{ ('%.2f' % r.target) if r.unit=='x' else ('%.1f%%' % (r.target*100)) }}</td>
<td><span class="pill" style="background:{{rag[r.status]}}">{{r.status}}</span></td></tr>{% endfor %}</table></div>

<h2>Analysis</h2>
<div class="grid">{% for f in figs %}<div class="card">{{ f|safe }}</div>{% endfor %}</div>
</main></body></html>
"""
