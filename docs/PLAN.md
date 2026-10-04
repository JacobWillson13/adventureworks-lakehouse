# Build plan

## Goal

A portfolio-grade Databricks lakehouse on the AdventureWorks sample database: a bronze/silver/gold pipeline,
a dbt star schema with tests and lineage, and three analyses on top of gold (sales exploration, customer
segmentation, product forecasting), plus two extensions (margin over time, supplier quality).
Every result is shown with the evidence behind it: job runs, data quality results, dbt tests, reconciliations.

## Architecture

```
data/raw (72 CSVs)
  -> [bronze]  PySpark job (src/01_bronze)        all columns STRING + lineage, row counts checked
  -> [silver]  Lakeflow Declarative Pipeline      typed, conformed, expectations = data quality record
  -> [gold]    dbt (dbt-databricks)                dims, facts, marts; tests, docs, lineage
  -> [analysis] Databricks notebooks on gold       MLflow-tracked clustering and forecasting
  -> [present]  AI/BI dashboard, figures in reports/figures, README
```

One Asset Bundle job orchestrates bronze -> pipeline -> dbt.

Why bronze is a job and not part of the pipeline: the raw export needs repairs Auto Loader cannot express
(ProductReview rows broken by unquoted line breaks, cp1252-encoded Address). Transformation logic lives in
`src/awlake` as plain functions so it stays testable with local Spark; pipeline files stay thin.

## Decisions (settled)

- Revenue = SubTotal (excludes tax and freight); TotalDue reconciled alongside.
- Forecast target = monthly units per product; revenue reported alongside.
- Cluster individual (online) customers; profile reseller stores separately.
- Extensions: margin over time, supplier quality.
- Analysis window ends 2014-05-31; June 2014 is a truncated extract.
- Silver uses Lakeflow Declarative Pipelines (chosen for learning value).
- `notebooks/00_local_prototype.ipynb` stays as the record of how the design was validated.
- Power BI is out of scope.

## Milestones

| # | Milestone | Done when | Jake writes |
|---|---|---|---|
| M1 | Databricks foundation | bundle deployed, bronze job green, `aw_bronze.ingest_audit` = 71 ok + 1 excluded | runs every command |
| M2 | Silver pipeline | 16 sales-domain tables typed with expectations; other tables follow later | first silver table + its expectations |
| M3 | Gold (dbt) | `dim_customer`, `dim_product`, `dim_territory`, `dim_date`, `fct_orders`, `fct_sales_lines`; reconciliation and channel tests pass; docs generated; `gold_dbt` task green on Databricks | Templated, including `fct_orders` (learning mode waived to save time; Jake reviews `fct_orders`, `stg_sales_order_header` and `sources.yml`) |
| M4 | Analysis on gold | prototype analyses rebuilt on gold, runs in MLflow, figures in `reports/figures`; marts built as each analysis needs them (e.g. monthly product units, customer features) | Templated (learning mode waived to save time; M4 and M5 share one branch and PR, `m4-m5-analysis-extensions`) |
| M5 | Extensions | margin (cost history joined by effective date), supplier quality | Templated, including the first effective-date join (learning mode waived; same branch and PR as M4) |
| M6 | Presentation | dashboard, GitHub Actions (ruff, pytest, dbt parse), README rewrite, repo public | Dashboard Overview page built in the UI; other pages, CI and README templated (Jake reviews) |

## Known data facts (from profiling and the prototype)

- 31,465 orders, 2011-05-31 to 2014-06-30; line totals reconcile to SubTotal within 0.01 per order (lines carry 6 decimals, headers 4).
- 121,317 order lines.
- Customer table: 18,484 individuals + 1,336 store rows (635 stores with orders, 701 store-only rows with no
  person and no orders).
- Channels never overlap: 635 reseller stores (all offline), 18,484 individuals (all online).
- July 2013 structural break: accessories and clothing launched online.
- Reseller orders arrive in monthly batches. Jun, Sep and Nov 2011 have none; Feb and Apr 2014 have only 3 and 2
  orders because those batches landed on Mar 1 and May 1.
- 64 reseller order lines (discontinued products sold after their last cost period ended on 2013-05-29) match no
  product cost period; margin carries the latest earlier cost forward for them.
- Purchase orders run 2011-04-16 to 2014-09-22 and are not truncated, so supplier quality uses all of them (the
  analysis window applies to sales only). There is no receipt date, and due date = order date + 14 days on
  99.4% of lines, so observed lead time cannot be measured; only the declared lead time (ProductVendor) varies.
