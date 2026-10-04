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
| M2 | Silver pipeline | sales-domain tables (about 12) typed with expectations; other tables follow later | first silver table + its expectations |
| M3 | Gold (dbt) | `dim_customer`, `dim_product`, `dim_territory`, `dim_date`, `fct_orders`, `fct_sales_lines`; reconciliation and channel tests pass; docs generated; `gold_dbt` task green on Databricks | `fct_orders` + its tests (staging was templated; Jake reads `stg_sales_order_header` and `sources.yml`) |
| M4 | Analysis on gold | prototype analyses rebuilt on gold, runs in MLflow, figures in `reports/figures`; marts built as each analysis needs them (e.g. monthly product units, customer features) | one analysis end to end |
| M5 | Extensions | margin (cost history joined by effective date), supplier quality | first effective-date join |
| M6 | Presentation | dashboard, GitHub Actions (ruff, pytest, dbt parse), README rewrite, repo public | README narrative |

## Known data facts (from profiling and the prototype)

- 31,465 orders, 2011-05-31 to 2014-06-30; line totals reconcile exactly to SubTotal.
- Channels never overlap: 635 reseller stores (all offline), 18,484 individuals (all online).
- July 2013 structural break: accessories and clothing launched online.
- Reseller orders arrive in monthly batches; some months have none (e.g. Feb and Apr 2014).
