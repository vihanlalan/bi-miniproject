# Strategic BI mini project: ShopSphere

End-to-end strategic Business Intelligence solution for a simulated online retailer.
Built for **DJS23SH2301L, Strategic Business Intelligence and Decision Engineering** (B.Tech AI and Data Science, Honors in Business Intelligence, Semester V), experiment 10: *Develop an end-to-end strategic BI solution for an enterprise use case*.

The full write-up is in [`report/BI_Miniproject_Report.pdf`](report/BI_Miniproject_Report.pdf).
Open [`outputs/dashboard.html`](outputs/dashboard.html) in a browser for the executive dashboard.

> All data is **synthetic**. Two problems are planted on purpose (Social CAC spike from Sep 2025, one vendor's delivery delays from Oct 2025) so the alert engine has something to find.

## What it does

| Syllabus unit | Feature | Module |
|---|---|---|
| 1 | Strategy-to-KPI link, scorecard | `bi/kpi.py` |
| 2 | Decision tree (churn), what-if levers, goal seek, tornado sensitivity, Monte Carlo, TOPSIS / weighted-sum vendor ranking | `bi/segmentation.py`, `bi/scenario.py`, `bi/mcdm.py` |
| 3 | Balanced scorecard (9 KPIs, RAG status), exception alerts (rules and z-scores), HTML executive dashboard | `bi/kpi.py`, `bi/alerts.py`, `bi/dashboard.py` |
| 4 | Finance (budget variance, margin by category), marketing (RFM, CLV vs CAC by channel), operations (vendor performance) | `bi/kpi.py`, `bi/segmentation.py` |
| 5 | Self-service what-if workbench (Streamlit) | `app.py` |
| 6 | ETL with data-quality log and checks, 12 automated tests | `bi/etl.py`, `tests/` |

Not built: HR analytics, cloud publishing (Power BI Service / Tableau Online) and natural-language query.

## Architecture

```
generate_data.py -> data/raw/*.csv -> etl.py -> SQLite star schema (data/warehouse.db)
                                                     |
        kpi / alerts / segmentation / scenario / mcdm  (analytics layer)
                                                     |
              dashboard.html   figures/*.png   results.json   app.py
```

Star schema: `fact_sales` (one row per order line) with `dim_date`, `dim_customer`, `dim_product`, `dim_vendor`; plus month-level `fact_marketing` and `fact_budget`. The `v_sales` view joins them. The CSVs in `outputs/` can be loaded into Power BI or Tableau as is.

## Run it

```bash
pip install -r requirements.txt
python -m bi.pipeline            # generate data, ETL, analytics, dashboard (about 45 s)
streamlit run app.py             # interactive what-if workbench
pytest                           # 12 tests
python report/build_report.py    # rebuild the PDF report
```

Set your name and roll number at the top of `report/build_report.py` before regenerating the report.

## Headline results (FY2025, simulated)

- Revenue Rs 5.53 crore, 92% of budget, +126% year on year. Gross margin 25.1% against a 28% target; promotion months run at about 18%.
- Scorecard: 5 Green, 3 Amber, 1 Red (gross margin).
- Alerts caught both planted problems: Social CAC (Rs 1,886 in Aug to Rs 5,063 in Oct) and Evergreen Imports on-time delivery (96% to 19%).
- Email returns 8.4x its CAC in lifetime value; Search 2.7x.
- A 5% supplier cost rise cuts contribution by about 20%; 20% more marketing adds about 2%.

## Assumptions to challenge

Price elasticity (-1.3) and the marketing response exponent (0.6) are assumptions, not estimates. They are inputs in the workbench and are varied in the Monte Carlo run.
