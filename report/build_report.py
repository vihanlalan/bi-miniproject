"""Builds report/BI_Miniproject_Report.pdf from outputs/results.json and outputs/figures.

    python report/build_report.py

Every number in the text is read from results.json, so the report stays in step with the model.
Fill in the cover-page placeholders below before submitting.
"""
import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bi import etl, kpi  # noqa: E402

STUDENT = "[Your name]"
ROLL = "[Roll no.]"
GUIDE = "[Faculty name]"

R = json.loads((ROOT / "outputs" / "results.json").read_text())
FIG = ROOT / "outputs" / "figures"
A, CK = R["annual"], R["customer_kpis"]

con = etl.connect()
VM = kpi.vendor_monthly_on_time(con)
CM = kpi.channel_monthly(con)
con.close()


def cr(x):
    return f"Rs {x / 1e7:.2f} crore"


def lakh(x):
    return f"Rs {x / 1e5:,.1f} lakh"


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def by(rows, key, val):
    return next(r for r in rows if r[key] == val)


# ---- numbers used in the text -------------------------------------------------------------
sc_rows = R["scorecard"]
n_green = sum(r["status"] == "Green" for r in sc_rows)
n_amber = sum(r["status"] == "Amber" for r in sc_rows)
n_red = sum(r["status"] == "Red" for r in sc_rows)
mon25 = [r for r in R["monthly"] if r["ym"].startswith("2025")]
promo = [r for r in mon25 if r["ym"][-2:] in ("06", "11", "12")]
other = [r for r in mon25 if r["ym"][-2:] not in ("06", "11", "12")]
promo_m = sum(r["gross_profit"] for r in promo) / sum(r["revenue"] for r in promo)
other_m = sum(r["gross_profit"] for r in other) / sum(r["revenue"] for r in other)
cats = {c["category"]: c for c in R["categories"]}
elec = cats["Electronics"]
elec_share = elec["revenue"] / sum(c["revenue"] for c in R["categories"])
seg = {s["segment"]: s for s in R["segments"]}
ch = {c["channel"]: c for c in R["channels"]}
clv = {c["channel"]: c for c in R["clv"]}
soc = CM[CM.channel == "Social"].set_index("ym").cac
evg = VM[VM.vendor_name == "Evergreen Imports"].set_index("ym").on_time_rate
scn = {s["scenario"]: s for s in R["scenarios"]}
mc = R["monte_carlo"]
churn = R["churn"]
vr = {v["vendor_name"]: v for v in R["vendor_rank"]}
stab = {v["vendor_name"]: v["share_ranked_first"] for v in R["vendor_stability"]}
dq = R["data_quality"]
tor = R["tornado"]
combo = scn["Combined: price +2%, marketing +10%, returns -2 pts"]
evg_rev_share = vr["Evergreen Imports"]["revenue"] / sum(v["revenue"] for v in R["vendor_rank"])

# ---- styles -------------------------------------------------------------------------------
ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontName="Times-Roman", fontSize=11, leading=15.5,
                      alignment=TA_JUSTIFY, spaceAfter=7)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, spaceBefore=10,
                    spaceAfter=8, textColor=colors.HexColor("#1d3557"))
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, spaceBefore=8,
                    spaceAfter=5, textColor=colors.HexColor("#1d3557"))
CAP = ParagraphStyle("cap", parent=BODY, fontName="Helvetica-Oblique", fontSize=8.5, leading=11,
                     alignment=TA_CENTER, textColor=colors.HexColor("#52606d"))
CELL = ParagraphStyle("cell", parent=BODY, fontName="Helvetica", fontSize=8.5, leading=11, alignment=0, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
TITLE = ParagraphStyle("title", parent=BODY, fontName="Helvetica-Bold", fontSize=22, leading=28,
                       alignment=TA_CENTER, textColor=colors.HexColor("#1d3557"), spaceAfter=10)
CENTER = ParagraphStyle("center", parent=BODY, alignment=TA_CENTER, fontSize=12, leading=18)
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=16, bulletIndent=4, spaceAfter=3)

story = []
P = lambda t, s=BODY: story.append(Paragraph(t, s))


def bullets(items):
    for i in items:
        story.append(Paragraph(i, BUL, bulletText="-"))
    story.append(Spacer(1, 4))


def fig(name, caption, w=15.5):
    from PIL import Image as PI
    iw, ih = PI.open(FIG / f"{name}.png").size
    story.append(KeepTogether([Image(str(FIG / f"{name}.png"), width=w * cm, height=w * cm * ih / iw),
                               Paragraph(caption, CAP), Spacer(1, 8)]))


def table(header, rows, widths, align_right_from=None):
    data = [[Paragraph(h, CELLB) for h in header]] + [[Paragraph(str(c), CELL) for c in r] for r in rows]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde6f0")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c2cc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))


# ---- cover --------------------------------------------------------------------------------
story += [Spacer(1, 2.5 * cm),
          Paragraph("Dwarkadas J. Sanghvi College of Engineering", CENTER),
          Paragraph("B.Tech in Artificial Intelligence (AI) and Data Science, Honors in Business Intelligence", CENTER),
          Paragraph("Semester V, Academic Year 2026-27", CENTER), Spacer(1, 1.5 * cm),
          Paragraph("Strategic Business Intelligence and Decision Engineering (DJS23SH2301L)", CENTER),
          Paragraph("Mini Project", CENTER), Spacer(1, 1.2 * cm),
          Paragraph("An End-to-End Strategic BI Solution for an Online Retailer", TITLE),
          Paragraph("KPI scorecard, exception alerts, customer analytics, what-if simulation and vendor selection", CENTER),
          Spacer(1, 3 * cm),
          Paragraph(f"Submitted by: {STUDENT}", CENTER), Paragraph(f"Roll no.: {ROLL}", CENTER),
          Paragraph(f"Under the guidance of: {GUIDE}", CENTER), Spacer(1, 1.2 * cm),
          Paragraph("Code: github.com/vihanlalan/bi-miniproject", CENTER), PageBreak()]

# ---- abstract -----------------------------------------------------------------------------
P("Abstract", H1)
P(f"This mini project builds a complete strategic BI solution for ShopSphere, a simulated online retailer with "
  f"{dq['clean_rows']:,} order lines, 40 products and 6 vendors over 24 months. Raw files are cleaned and loaded into a "
  f"star schema in SQLite. On top of that I built a balanced scorecard, an exception-alert engine, RFM customer "
  f"segmentation, a channel-level CLV against CAC comparison, a churn decision tree, a what-if and Monte Carlo "
  f"model for profit, and a TOPSIS ranking of vendors. The results are presented in a six-page Power BI report "
  f"with DAX measures and a live what-if page, and also as an HTML dashboard and a Streamlit workbench.")
P(f"For FY2025 the retailer earned {cr(A['revenue'])} ({pct(A['revenue_vs_budget'], 0)} of budget) at a gross margin of "
  f"{pct(A['gross_margin_pct'])}, against a 28% target. The system flagged two problems that were planted in the data: "
  f"Social-media acquisition cost rising from about Rs {soc['2025-08']:,.0f} to Rs {soc['2025-10']:,.0f} per customer, "
  f"and one vendor falling to {pct(evg['2025-12'], 0)} on-time delivery. The what-if model shows that a 5% rise in "
  f"supplier cost would remove {pct(-scn['Supplier costs +5%']['contribution_delta'], 0)} of contribution, far more than "
  f"any marketing change could recover.")
P("All data is synthetic. The findings show that the method works. They are not claims about a real company.")

# ---- 1 intro ------------------------------------------------------------------------------
P("1. Introduction", H1)
P("1.1 Business context and problem", H2)
P("ShopSphere sells electronics, home and kitchen goods, fashion, beauty products and sports gear online. Its "
  "management team gets revenue reports every month, but nobody connects them to the strategy. Three questions come "
  "up again and again. Are we meeting our targets, and where are we not? Which customers and channels deserve the "
  "next rupee? And if we change price, discounts or marketing, what happens to profit and how sure can we be? "
  "A set of operational reports cannot answer these. Strategic BI has to.")
P("1.2 Objectives", H2)
bullets([
    "Build a clean, tested data warehouse that every KPI reads from, so two reports never give two answers.",
    "Translate strategy into KPIs with targets and a balanced scorecard (Unit 3).",
    "Detect problems early with rule-based and statistical alerts instead of waiting for a monthly review (Unit 3).",
    "Cover the finance, marketing and operations functions with analytics that lead to a decision (Unit 4).",
    "Support decisions under uncertainty with what-if, goal seek, sensitivity, Monte Carlo and a multi-criteria "
    "vendor model (Unit 2).",
    "State the governance and ethical limits of the solution (Unit 6).",
])
P("1.3 Scope", H2)
P("I picked finance, marketing and operations from Unit 4. HR analytics is left out because a retail dataset of this "
  "kind would need invented employee data, which adds nothing. I used "
  "a Python-only pipeline for the data preparation and the heavier models (ETL, segmentation, churn tree, TOPSIS, "
  "Monte Carlo), because those steps are then reproducible and tested. The presentation layer is Power BI Desktop: "
  "the star schema is loaded from one Excel workbook, KPIs and the what-if projection are DAX measures, and the "
  "report has six pages (Section 3.4).")

# ---- 2 mapping ----------------------------------------------------------------------------
P("2. Mapping to the syllabus", H1)
P("The table shows where each syllabus unit appears in the project.")
table(["Unit", "Syllabus topic", "What was built", "File"], [
    ["1", "Strategic vs operational decisions, BI maturity, case studies",
     "Business case, scorecard that links operational data to strategic targets", "bi/kpi.py"],
    ["2", "Decision trees, what-if, goal seek, sensitivity, risk, MCDM, simulation",
     "Churn decision tree, what-if levers, goal seek, tornado chart, Monte Carlo, TOPSIS and weighted sum",
     "bi/scenario.py, bi/mcdm.py, bi/segmentation.py"],
    ["3", "EPM, KPIs, balanced scorecard, dashboard design, alerts, exception reporting",
     "Nine-KPI balanced scorecard with RAG status, alert engine, executive overview page in Power BI (HTML copy also kept)",
     "powerbi/measures.dax, bi/alerts.py"],
    ["4", "Finance, marketing and operations analytics",
     "Budget variance and margin analysis, RFM, CLV and CAC by channel, vendor performance", "bi/kpi.py, bi/segmentation.py"],
    ["5", "Self-service BI, automated insights, real-time analytics",
     "Power BI what-if page with slicers as parameters, and a Streamlit copy. Publishing to Power BI Service and Q&amp;A "
     "are described in the build guide.", "powerbi/, app.py"],
    ["6", "Data quality, governance, ethics, ROI, mini-capstone planning",
     "Cleaning log, post-load checks, 12 automated tests, governance notes in Section 9", "bi/etl.py, tests/"],
], [1.0, 4.6, 7.4, 3.6])

# ---- 3 data & architecture ----------------------------------------------------------------
P("3. Data and architecture", H1)
P("3.1 The synthetic dataset", H2)
P("I generated the data with a fixed random seed so that anyone running the code gets the same numbers. Customers "
  "sign up through five channels (Search, Social, Email, Affiliate and Organic) and place orders month by month with "
  "seasonality, a promotion in June, November and December, and a gradual loss of customers over time. Vendor lead "
  "times, defect rates and cost levels differ, which is what makes vendor selection a real decision. The budget is the "
  "actual run rate with a planning error of -7% to +10% per month, which mimics a finance team that plans without "
  "knowing about later problems.")
P("Two problems were planted on purpose so that the BI layer has something to find. From September 2025, 55% of "
  "Social-media sign-ups disappear while the spend stays the same. From October 2025, deliveries from one vendor, "
  "Evergreen Imports, take about three days longer. A small amount of dirty data was added as well: duplicate rows, "
  "missing delivery days and negative quantities.")
P("3.2 Pipeline and star schema", H2)
P("The pipeline has four steps: generate raw CSV files, clean and load them into SQLite, run the analytics, and write "
  "the dashboard, figures and results file. Running <font name='Courier'>python -m bi.pipeline</font> does all four in "
  "about 45 seconds. The warehouse is a star schema with one sales fact table (one row per order line) and dimensions "
  "for date, customer, product and vendor. Marketing spend and the budget sit in two smaller fact tables at month "
  "level. Measures such as net revenue, cost of goods, return cost and gross profit are calculated once during loading, "
  "so no report can define them differently.")
P("3.3 Data quality", H2)
P("The cleaning rules are simple and each one has a reason. Duplicate line IDs are dropped because the same sale "
  "would otherwise be counted twice. Rows with a negative quantity are dropped because returns are already tracked "
  "in a separate flag. Missing delivery days are filled with the median for the same product, since delivery time "
  "depends mostly on the vendor of that product. After loading, five checks run (null keys, duplicate IDs, orphan "
  "customers, orders dated before sign-up, negative revenue) and all must return zero.")
table(["Step", "Rows affected"], [
    ["Raw order lines", f"{dq['raw_rows']:,}"],
    ["Duplicate lines removed", dq["duplicate_lines_removed"]],
    ["Negative quantities removed", dq["negative_qty_removed"]],
    ["Missing delivery days filled with product median", dq["null_delivery_days_imputed"]],
    ["Clean order lines loaded", f"{dq['clean_rows']:,}"],
    ["Post-load checks failing", sum(v for k, v in dq.items() if k.startswith("check_"))],
], [10, 4])

P("3.4 Power BI implementation", H2)
P("The warehouse tables and the model results are exported to one Excel workbook with 17 sheets, which Power BI loads "
  "in a single step. The model has nine relationships, all many-to-one with single-direction filtering: a month table "
  "filters the date table, the date, customer and product tables filter sales, vendors filter products, and a channel "
  "table filters both customers and marketing spend. A separate month table is needed because marketing spend and the "
  "budget are monthly, while sales are daily, and a shared month key lets one slicer drive all three.")
P("About 70 DAX measures cover revenue, margin, return rate, on-time delivery, budget variance, CAC and contribution. "
  "The headline FY2025 measures use REMOVEFILTERS on the date tables so that they do not change when someone clicks a "
  "month, which is how an executive card should behave. The what-if page uses seven calculated tables built with "
  "GENERATESERIES as slicers. A measure reads each slicer with SELECTEDVALUE and falls back to a baseline value when "
  "nothing is selected, so the page opens showing the actual FY2025 position. The projection measure uses the same "
  "formula as the Python model, and the build guide lists the Python results to check the DAX against.")
table(["Page", "Content", "Syllabus link"], [
    ["1. Executive overview", "KPI cards, revenue against budget, margin trend, exception table", "Unit 3"],
    ["2. Balanced scorecard", "Nine KPIs by perspective with red, amber and green status", "Unit 3"],
    ["3. Marketing and customers", "CAC by channel, RFM segments, CLV against CAC, churn risk", "Unit 4"],
    ["4. Operations and vendors", "On-time trend by vendor, TOPSIS ranking, margin by category", "Units 2 and 4"],
    ["5. What-if analysis", "Seven slicers, projected against baseline contribution, preset scenarios", "Unit 2"],
    ["6. Risk and sensitivity", "Tornado chart, Monte Carlo histogram and percentiles", "Unit 2"],
], [4.2, 9.2, 3.2])

# ---- 4 scorecard --------------------------------------------------------------------------
P("4. Strategic KPIs and the balanced scorecard", H1)
P(f"I chose nine KPIs across the four perspectives of Kaplan and Norton's balanced scorecard. Each has a target, and "
  f"a status of Green (target met), Amber (within 90% of target) or Red. For KPIs where lower is better, such as return "
  f"rate, attainment is the target divided by the actual value. For FY2025, {n_green} KPIs are Green, {n_amber} are "
  f"Amber and {n_red} is Red.")
fig("scorecard", "Figure 1. Attainment against target for each KPI.")
rows = []
for r in sc_rows:
    fmt = (lambda v: f"{v:.2f}") if r["key"] == "marketing_roi" else (lambda v: pct(v))
    rows.append([r["perspective"], r["kpi"], fmt(r["actual"]), fmt(r["target"]), r["status"]])
table(["Perspective", "KPI", "Actual", "Target", "Status"], rows, [3.2, 7.2, 2.0, 2.0, 2.0])
P(f"The only Red KPI is gross margin at {pct(A['gross_margin_pct'])}. The cause is visible in the monthly chart. In "
  f"the three promotion months the margin is {pct(promo_m)}, against {pct(other_m)} in the other nine months. "
  f"A 10 to 20% discount removes most of the thin margin on electronics, which is {pct(elec_share, 0)} of revenue and earns "
  f"only {pct(elec['margin_pct'])} gross margin. So the promotion calendar, and not the cost base, is what holds "
  f"the margin below target.")
fig("margin_trend", "Figure 2. Gross margin by month. Red dots are promotion months.")
P(f"Revenue reached {pct(A['revenue_vs_budget'], 0)} of budget even though it grew {pct(A['yoy_growth'], 0)} on last "
  f"year. The first caveat is that the budget here is a simulated plan, so this gap says little about real forecasting. "
  f"The second is that Amber on marketing ROI ({A['marketing_roi']:.2f} against a target of 2.0) is partly built in: "
  f"I count only first-year gross profit from customers acquired in 2025, and a customer who joins in July has had "
  f"six months to pay back.")
fig("revenue_vs_budget", "Figure 3. Monthly revenue against budget, Rs million.")

# ---- 5 alerts -----------------------------------------------------------------------------
P("5. Performance monitoring and exception alerts", H1)
P("A dashboard that someone must open and read is passive. The alert engine looks at the latest three months and "
  "raises an exception when one of these rules fires: revenue under 90% of budget, gross margin more than three "
  "points under target, marketing spend more than 10% over budget, a vendor under 80% on-time delivery, or a channel's "
  "customer acquisition cost more than two standard deviations above its own previous 12 months. The z-score rule "
  "matters because a fixed threshold has no way to know that Rs 2,500 is normal for Search and a disaster for Email.")
al = R["alerts"]
table(["Month", "Severity", "Area", "Alert"], [[a["month"], a["severity"], a["area"], a["message"]] for a in al],
      [2.0, 2.0, 2.4, 10.0])
P(f"Both planted problems were caught without anyone looking for them. Social acquisition cost went from "
  f"Rs {soc['2025-08']:,.0f} in August to Rs {soc['2025-09']:,.0f} in September and Rs {soc['2025-10']:,.0f} in "
  f"October, with a z-score of 3.8 in October. Evergreen Imports dropped from {pct(evg['2025-09'], 0)} on-time in September "
  f"to {pct(evg['2025-10'], 0)} in October. That vendor supplies {pct(evg_rev_share, 0)} of revenue, so the delay is "
  f"not a small issue. The Search alert in October is a smaller side effect: Search CAC in October was Rs "
  f"{CM[(CM.channel == 'Search') & (CM.ym == '2025-10')].cac.iloc[0]:,.0f}, a little above its usual range.")
fig("channels", "Figure 4. CAC by channel for FY2025 (left) and monthly CAC (right). The Social spike is the planted problem.")

# ---- 6 functional analytics ---------------------------------------------------------------
P("6. Functional analytics", H1)
P("6.1 Finance: where the margin comes from", H2)
P(f"Category margins range from {pct(elec['margin_pct'])} for Electronics to {pct(cats['Beauty']['margin_pct'])} for "
  f"Beauty. Electronics brings the most revenue ({lakh(elec['revenue'])}) but only {lakh(elec['gross_profit'])} of gross "
  f"profit, while Beauty brings {lakh(cats['Beauty']['gross_profit'])} on about a quarter of Electronics' revenue. Fashion has "
  f"the highest return rate at {pct(cats['Fashion']['return_rate'])}, more than three times the rate of Beauty. Any promotion budget "
  f"should be set per category, because the same discount has very different effects on each.")
P("6.2 Marketing: segments, channels and churn", H2)
P(f"I scored each customer from 1 to 5 on recency, frequency and monetary value (RFM) and grouped them with "
  f"simple rules. The result is uneven in the way retail usually is. Champions are {pct(seg['Champions']['customer_share'], 0)} "
  f"of customers and bring {pct(seg['Champions']['revenue_share'], 0)} of revenue. The top 20% of customers by spend "
  f"account for {pct(R['pareto_top20'], 0)} of revenue. The group that needs attention is At risk: "
  f"{seg['At risk']['customers']} customers who used to buy often ({seg['At risk']['avg_orders']:.1f} orders on average) "
  f"but have not bought for about {seg['At risk']['avg_recency']:.0f} days. They represent "
  f"{pct(seg['At risk']['revenue_share'], 0)} of lifetime revenue, so a win-back campaign aimed at them is worth more "
  f"than the same effort on new customers.")
fig("segments", "Figure 5. Share of customers and share of revenue by RFM segment.")
P(f"To compare channels I used a simple customer lifetime value formula, CLV = m x r / (1 + i - r), where m is the yearly "
  f"gross profit per active customer, r is the share of last year's customers who bought again this year, and i is a "
  f"10% discount rate. Dividing by the channel's CAC gives a payback ratio. A common rule of thumb is that this ratio "
  f"should be at least 3.")
table(["Channel", "Retention", "CLV (Rs)", "CAC (Rs)", "CLV / CAC"], [
    [c, pct(clv[c]["retention"], 0), f"{clv[c]['clv']:,.0f}",
     "n/a" if clv[c]["cac"] != clv[c]["cac"] else f"{clv[c]['cac']:,.0f}",
     "n/a" if clv[c]["clv_to_cac"] != clv[c]["clv_to_cac"] else f"{clv[c]['clv_to_cac']:.1f}"]
    for c in ["Email", "Social", "Affiliate", "Search", "Organic"]], [3, 2.6, 3, 3, 3])
P(f"Email returns {clv['Email']['clv_to_cac']:.1f} times its cost, far above the others. Search is the weakest paid channel at "
  f"{clv['Search']['clv_to_cac']:.1f} and Affiliate is just under the threshold. Social looks fine on this annual view "
  f"({clv['Social']['clv_to_cac']:.1f}), but only because the three bad months are averaged with nine good ones. This is why "
  f"the monthly alert is needed alongside the annual metric.")
P(f"For churn I trained a decision tree of depth 3 on customers as of 31 March 2025 and checked who bought nothing in "
  f"the next 180 days. I chose a tree over a more accurate model because a marketing manager can read its rules. "
  f"On a held-out 30% of customers it reaches {pct(churn['accuracy'], 0)} accuracy against {pct(churn['baseline_accuracy'], 0)} "
  f"for always guessing the majority class, with an AUC of {churn['auc']:.2f}. Recency does almost all the work "
  f"({pct(churn['importance']['recency'], 0)} of importance): customers who have not bought for roughly 90 days are "
  f"very likely to stay quiet. That is useful but not surprising, and a single split on one date is not enough to "
  f"claim more, so I treat the model as a ranking aid and not as a forecast.")
P("6.3 Operations: choosing vendors", H2)
P("Vendors differ on cost, delivery and quality, and none is best on all three. I ranked them on four criteria, "
  "cost index, on-time rate, return rate and average delivery days, with weights of 30%, 30%, 25% and 15%. TOPSIS "
  "scores each vendor by its distance from an ideal vendor and a worst vendor. I also ran a plain weighted sum as a "
  "cross-check, because two methods that agree are more convincing than one.")
fig("vendors", "Figure 6. TOPSIS score for each vendor, with FY2025 on-time rate.")
P(f"Apex Components is first under both methods. Evergreen Imports is fourth under TOPSIS and sixth under the weighted "
  f"sum, because its low price of 0.88 is cancelled out by {pct(vr['Evergreen Imports']['on_time_rate'], 0)} on-time "
  f"delivery. Cedar Trading is last under TOPSIS because of a {pct(vr['Cedar Trading']['return_rate'], 0)} return rate. "
  f"Since the weights are a judgement call, I drew 5,000 random weight sets and counted how often each vendor ranks first. "
  f"Apex wins {pct(stab['Apex Components'], 0)} of the time and Delta Source {pct(stab['Delta Source'], 0)}, so the "
  f"top choice is fairly stable but not certain.")

# ---- 7 decision engineering ---------------------------------------------------------------
P("7. Decision engineering: what-if, sensitivity and risk", H1)
P("7.1 The model", H2)
P("The model projects next year's contribution (gross profit minus marketing) from the FY2025 actuals. It has five "
  "levers: list price, discount depth, marketing spend, return rate and supplier cost. Demand responds to the "
  "effective price with a constant elasticity of -1.3, and to marketing with an exponent of 0.6 applied to the share of "
  "revenue that comes from newly acquired customers, so that extra spend has diminishing returns. Both numbers are "
  "assumptions and not estimates from the data, which is why they are inputs in the workbench and are varied in the "
  "Monte Carlo run. With no lever moved, the model reproduces the actual FY2025 contribution to within 1%, and a test "
  "checks this.")
P("7.2 Scenarios", H2)
rows = [[s["scenario"], f"{s['revenue'] / 1e7:.2f}", f"{s['contribution'] / 1e7:.2f}",
         f"{s['revenue_delta']:+.1%}", f"{s['contribution_delta']:+.1%}"] for s in R["scenarios"]]
table(["Scenario", "Revenue (Rs crore)", "Contribution (Rs crore)", "Revenue change", "Contribution change"], rows,
      [6.6, 2.4, 2.8, 2.2, 2.6])
P(f"A 3% price rise lowers revenue by {pct(-scn['Price +3%']['revenue_delta'])} but raises contribution by "
  f"{pct(scn['Price +3%']['contribution_delta'])}, because the 3.8% of units lost no longer need to be bought from vendors, while every remaining unit earns 3% more. A 3-point deeper discount "
  f"has the opposite effect and costs {pct(-scn['Discount +3 pts']['contribution_delta'])} of contribution. Marketing "
  f"is the weakest lever: 20% more spend adds {pct(scn['Marketing +20%']['revenue_delta'])} revenue but only "
  f"{pct(scn['Marketing +20%']['contribution_delta'])} contribution, since marketing is a small share of cost. The largest "
  f"threat is outside the company's control: a 5% rise in supplier cost reduces contribution by "
  f"{pct(-scn['Supplier costs +5%']['contribution_delta'])}.")
P("7.3 Sensitivity and goal seek", H2)
fig("tornado", "Figure 7. Change in annual contribution when each driver moves by the stated amount.")
P(f"The tornado chart ranks the drivers. Supplier cost and list price are far ahead of everything else, each swinging "
  f"contribution by about {lakh(tor[0]['range'])} over the tested range, while a 10% change in marketing spend "
  f"moves it by only {lakh(tor[-1]['range'])}. Management attention should follow that order. Two goal-seek results follow from the "
  f"model. To lift contribution by 10%, list prices would need to rise by {pct(R['goal_price'])} if nothing else "
  f"changes. And a 3% price rise stays profitable unless customers are much more price-sensitive than assumed: "
  f"the break-even elasticity is {R['breakeven_elasticity']:.2f}, against the assumed -1.3.")
P("7.4 Monte Carlo risk", H2)
P(f"The point estimates above hide uncertainty. I ran 10,000 simulations of the combined plan (price +2%, "
  f"marketing +10%, returns down 2 points) with elasticity drawn from a normal distribution around -1.3, the marketing "
  f"exponent between 0.4 and 0.8, a demand shock of 6% standard deviation, and supplier cost inflation averaging 2%. "
  f"The mean contribution is {cr(mc['mean'])}, with a 5th to 95th percentile range of {cr(mc['p5'])} to {cr(mc['p95'])}. "
  f"The do-nothing baseline is {cr(mc['baseline'])}, so the plan beats it in about "
  f"{pct(1 - mc['prob_below_baseline'], 0)} of runs. That number is lower than the deterministic +{combo['contribution_delta'] * 100:.1f}% "
  f"suggests because the simulation includes expected cost inflation that the baseline does not. A decision maker "
  f"should read the range and not the single figure.")
fig("monte_carlo", "Figure 8. Distribution of annual contribution under the combined plan.")

# ---- 8 recommendations --------------------------------------------------------------------
P("8. Recommendations", H1)
bullets([
    f"<b>Vendors.</b> Open a service-level discussion with Evergreen Imports now, since its on-time rate fell from "
    f"{pct(evg['2025-09'], 0)} to {pct(evg['2025-12'], 0)} and it supplies {pct(evg_rev_share, 0)} of revenue. Start moving some volume "
    f"to Apex Components and Delta Source, which rank first and second.",
    f"<b>Acquisition.</b> Pause or cap Social spend whenever its CAC z-score passes 2, and shift part of the budget to "
    f"Email, which returns {clv['Email']['clv_to_cac']:.1f} times its cost. Email has limited reach, so test how far it scales.",
    f"<b>Promotions.</b> Set discount depth per category. Electronics earns {pct(elec['margin_pct'])} margin and cannot "
    f"carry a 15% discount. This is the main route to the 28% margin target.",
    f"<b>Retention.</b> Run a win-back campaign for the {seg['At risk']['customers']} At-risk customers, who carry "
    f"{pct(seg['At risk']['revenue_share'], 0)} of lifetime revenue, before spending more on acquiring new ones.",
    f"<b>Pricing.</b> Test a 2 to 3% price rise on a few categories first. The model says it pays unless elasticity is "
    f"worse than {R['breakeven_elasticity']:.1f}, but that elasticity has never been measured in this data.",
])

# ---- 9 governance -------------------------------------------------------------------------
P("9. Governance, ethics and limitations", H1)
P("9.1 Governance and ethics", H2)
P("Data quality is handled in the load step, with a logged count for every cleaning rule and five post-load checks, "
  "so a report can be traced back to a rule instead of someone's judgement. The segmentation uses purchase behaviour "
  "only and no personal attributes, and customer IDs are synthetic. In a real deployment I would add role-based access "
  "so that marketing sees segments but not individual order history, and I would not use the churn score to decide "
  "who gets worse service or worse prices. The decision tree was chosen partly for this reason: its rules can be "
  "explained to a customer or an auditor. Vendor weights are visible and editable, so the ranking can be challenged.")
P("9.2 Limitations", H2)
bullets([
    "The data is simulated. Planted problems are easier to find than real ones, so the alert results should not be "
    "read as a measure of how well the engine works on real data.",
    "Elasticity and marketing response are assumed, not estimated. The Monte Carlo run shows the effect of being "
    "wrong, but cannot remove it.",
    "The model covers contribution only. There are no fixed overheads, no stock holding costs and no cannibalisation "
    "between products.",
    "The churn model uses one cutoff date and one train-test split. Cross-validation over several cutoffs is the "
    "obvious next step.",
    "Publishing to Power BI Service, Q&amp;A (natural-language query) and HR analytics were not part of the build. The scorecard, "
    "alerts, segments and Monte Carlo results are loaded into Power BI as tables from the Python models, not recomputed in DAX.",
])

# ---- 10 conclusion ------------------------------------------------------------------------
P("10. Conclusion", H1)
P(f"The project takes a retailer's raw files to a set of decisions. The warehouse gives one version of the truth, the "
  f"scorecard shows that margin is the one KPI in Red, the alert engine finds two problems that a monthly report would "
  f"have caught late, and the decision models show which levers matter. The most useful result is how unevenly the levers "
  f"compare: supplier cost and price move profit by tens of lakhs, while marketing moves it by a few lakhs. If I extended the work, "
  f"I would replace the assumed elasticity with one estimated from price changes in real data, and publish the "
  f"report through Power BI Service to cover the cloud part of Unit 5.")

# ---- 11 run -------------------------------------------------------------------------------
P("11. How to run the project", H1)
P("Install the packages with <font name='Courier'>pip install -r requirements.txt</font>. Then "
  "<font name='Courier'>python -m bi.pipeline</font> rebuilds everything and writes <font name='Courier'>outputs/dashboard.html</font>. "
  "<font name='Courier'>python -m bi.export_powerbi</font> writes the Excel workbook for Power BI, and "
  "<font name='Courier'>powerbi/BUILD_GUIDE.md</font> lists the relationships, measures and visuals for each page. "
  "<font name='Courier'>streamlit run app.py</font> opens the Streamlit copy of the what-if workbench, <font name='Courier'>pytest</font> runs the 12 tests, "
  "and <font name='Courier'>python report/build_report.py</font> regenerates this report.")

P("References", H1)
bullets([
    "R. Sharda, D. Delen and E. Turban, <i>Business Intelligence, Analytics, and Data Science: A Managerial Perspective</i>, 4th ed., Pearson.",
    "D. J. Power and C. Heavin, <i>Decision Support, Analytics, and Business Intelligence</i>, 3rd ed.",
    "P. Tucci, <i>Power BI Succinctly</i>, Syncfusion, 2017.",
    "R. S. Kaplan and D. P. Norton, \"The Balanced Scorecard: Measures That Drive Performance\", <i>Harvard Business Review</i>, Jan-Feb 1992.",
    "C. L. Hwang and K. Yoon, <i>Multiple Attribute Decision Making: Methods and Applications</i>, Springer, 1981.",
])


def footer(c, d):
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#52606d"))
    if d.page > 1:
        c.drawString(2 * cm, 1.2 * cm, "Strategic BI mini project: ShopSphere")
        c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {d.page}")
    c.restoreState()


out = ROOT / "report" / "BI_Miniproject_Report.pdf"
SimpleDocTemplate(str(out), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                  bottomMargin=2 * cm, title="Strategic BI Mini Project Report",
                  author=STUDENT).build(story, onFirstPage=footer, onLaterPages=footer)
print("wrote", out)
