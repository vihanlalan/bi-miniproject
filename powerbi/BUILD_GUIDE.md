# Building the ShopSphere report in Power BI Desktop

About 60 to 90 minutes. Everything the report needs is prepared: the data model is in one Excel file, the
measures are in `measures.dax`, and the colours are in `ShopSphere_theme.json`.

> I could not open Power BI Desktop where this was prepared, so the `.pbix` file itself is not in the repo.
> The steps below build it. Check your numbers against the table in section 6 before showing it.

## 1. Load the data

1. Power BI Desktop > **Get data > Excel workbook** > `powerbi/ShopSphere_BI_Data.xlsx`.
2. Tick **all 17 sheets** > **Load** (no transform needed, types are already correct).
3. **View > Themes > Browse for themes** > `ShopSphere_theme.json`.

## 2. Model view: relationships

Drag to create these (all many-to-one, single direction, one side listed first):

| One side | Many side |
|---|---|
| dim_month[ym] | dim_date[ym] |
| dim_date[date_key] | fact_sales[date_key] |
| dim_customer[customer_id] | fact_sales[customer_id] |
| dim_product[product_id] | fact_sales[product_id] |
| dim_vendor[vendor_id] | dim_product[vendor_id] |
| dim_channel[channel] | dim_customer[channel] |
| dim_channel[channel] | fact_marketing[channel] |
| dim_month[ym] | fact_marketing[ym] |
| dim_month[ym] | fact_budget[ym] |

Leave these tables **unrelated** (they are static results from the Python models): `scorecard`, `alerts`,
`scenarios`, `tornado`, `clv_by_channel`, `categories`, `monte_carlo_hist`, `monte_carlo_summary`.

Set **dim_month[month_label]** to *Sort by column* > `month_start`. Hide the key columns in fact tables.

## 3. Measures

1. **Home > Enter data**, create a one-column table named `Measures`, load, then delete the blank column.
2. Open `measures.dax`. Create each measure with **Modeling > New measure** (copy one block at a time).
3. For the seven what-if tables (section 5 of the file) use **Modeling > New table** instead.
4. Format: money measures as Currency (0 decimals), `%` measures as Percentage (1 decimal).

## 4. Pages

Use 16:9 pages, theme background, a dark blue title bar on each page. Slicers on every page except page 5:
`dim_month[fiscal_year]` (tile style) and `dim_channel[channel]` where relevant.

### Page 1: Executive overview (Unit 3: EPM, executive dashboard)
- 5 cards: `Revenue FY2025`, `Revenue vs Budget FY2025`, `Gross Margin FY2025`, `Contribution FY2025`, `On-time FY2025`.
  Set the font colour of the margin and on-time cards with conditional formatting.
- Combo chart: X = `dim_month[month_label]`, columns = `Revenue`, line = `Revenue Budget`.
- Line chart: X = `dim_month[month_label]`, Y = `Gross Margin %`, plus a constant line at 28% (Analytics pane).
- Table from `alerts`: month, severity, area, message (this is the exception report). Colour `severity`
  with rules: High = red, Medium = amber, Low = grey.

### Page 2: Balanced scorecard (Unit 3: KPIs, balanced scorecard)
- Matrix from `scorecard`: rows = perspective, kpi; values = actual, target, attainment, status.
  Sort by `sort`. Conditional formatting on `status` (Format > Cell elements > Background colour > Rules):
  Green `#2e8b57`, Amber `#d4a017`, Red `#c0392b`, text white.
- Bar chart: Y = kpi, X = attainment, with a constant line at 1.
- Text box that states the one Red KPI (gross margin) and why (promotion months).

### Page 3: Marketing and customers (Unit 4: marketing analytics)
- Line chart: X = `dim_month[month_label]`, Y = `CAC`, legend = `dim_channel[channel]`. The Social spike is the story.
- Clustered column: X = `dim_customer[segment]`, Y = `Customer Share %` and `Revenue Share %`.
- Table from `clv_by_channel`: channel, retention, clv, cac, clv_to_cac.
- Card: `High Churn Risk Customers`. Slicer on `dim_customer[churn_risk_band]`.
- Treemap: group = segment, values = `Lifetime Revenue`.

### Page 4: Operations and vendors (Unit 4: supply chain, Unit 2: MCDM)
- Line chart: X = `dim_month[month_label]`, Y = `On-time %`, legend = `dim_vendor[vendor_name]`. Evergreen falls from Oct 2025.
- Bar chart: Y = `dim_vendor[vendor_name]`, X = `dim_vendor[topsis]` (set aggregation to *Don't summarize / Maximum*).
- Table: vendor_name, cost_index, `On-time %`, `Return Rate`, topsis, weighted_sum, topsis_rank, wsm_rank, share_ranked_first.
- Bar by `dim_product[category]`: `Gross Margin %` (finance angle: Electronics is lowest).

### Page 5: What-if analysis (Unit 2: what-if, scenario planning, goal seek)
- Seven single-select slicers from the what-if tables: Price Change %, Discount Change pts, Marketing Change %,
  Return Rate Change pts, Supplier Cost Change %, Elasticity x10, Marketing Exponent x100.
  Do not select anything in them at first: the measures then use the baseline (no change, elasticity -1.3, exponent 0.6).
- Cards: `Baseline Contribution`, `Projected Contribution`, `Contribution Change %`, `Projected Revenue`, `Revenue Change %`.
- Table from `scenarios` (the nine preset scenarios) and a bar chart of `contribution_delta`.
- Goal seek by slicer: move Price Change % until `Contribution Change %` reaches 10%. The answer is +3%.

### Page 6: Risk and sensitivity (Unit 2: risk analysis, simulation)
- Clustered bar from `tornado`: Y = driver, X = `downside` and `upside`. Overlap the bars (Format > Bars > Space between series 0).
- Column chart from `monte_carlo_hist`: X = `contribution_rs_million`, Y = `runs`.
- Table from `monte_carlo_summary` (baseline, mean, P5, median, P95, probability below baseline).

## 5. Publishing (Unit 5: cloud BI)

If you have a work or college account: **Home > Publish > My workspace**, then in the Service open the report,
**Pin to a dashboard**, and try **Q&A** (natural-language query) on the dashboard. This is the part of Unit 5
that is not in the repo, so doing it live in front of ma'am is worth the extra five minutes.

## 6. Check your numbers

These come from the tested Python model. If Power BI shows something different, a relationship or measure is wrong.

| Check | Expected |
|---|---|
| `Revenue FY2025` | Rs 5,53,17,301 (5.53 crore) |
| `Revenue vs Budget FY2025` | 92.4% |
| `Gross Margin FY2025` | 25.1% |
| `Contribution FY2025` | Rs 1,02,68,181 |
| `On-time FY2025` | 86.2% |
| `Return Rate FY2025` | 8.2% |
| `Marketing ROI FY2025` | 1.83 |
| `Baseline Contribution` / `Projected Contribution` (no slicers) | 1,02,68,181 / 1,02,90,644 (the model reproduces actuals within 0.3%) |
| Price Change +3% | Projected Contribution 1,13,41,170; Projected Revenue 5,48,28,935 |
| Supplier Cost +5% | Projected Contribution 82,58,205 |
| Marketing +20% | Projected Contribution 1,04,99,457 |
| Price +2%, Marketing +10%, Returns -2 pts | Projected Contribution 1,16,69,875 |
| Social CAC in Oct 2025 | about Rs 5,063 |
| Evergreen `On-time %` in Dec 2025 | about 20% |

## 7. Where each piece comes from

Python does the heavy modelling (ETL, RFM, churn tree, TOPSIS, Monte Carlo) and Power BI presents it and
recomputes the KPIs and the what-if projection live. If asked why the scorecard and alerts are tables and not DAX:
they come from the same pipeline that is tested in `tests/`, and the thresholds are in `bi/config.py`.
To regenerate the workbook after changing anything: `python -m bi.export_powerbi`.
