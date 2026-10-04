# `fct_orders`: design spec

`fct_orders` is the order-level fact. This spec defined what the model must contain and how to check it before
it was written; the model is `dbt/models/marts/fct_orders.sql` and all checks below pass on Databricks.

## Where it goes

- Model: `dbt/models/marts/fct_orders.sql`. It is materialized as a table automatically, because
  `dbt_project.yml` sets `+materialized: table` for everything under `marts/`.
- Docs and tests: a new `- name: fct_orders` entry in `dbt/models/marts/_marts.yml`.
- Any singular tests: `dbt/tests/`, next to `assert_sales_lines_reconcile_to_order_subtotal.sql`.

## Grain

**One row per sales order.** 31,465 rows on the current export, one for every row in `stg_sales_order_header`.
Do not filter to the analysis window here. Like `fct_sales_lines`, the fact keeps every order. Analyses
filter through `dim_date.is_in_analysis_window`.

## Columns

| Column | Meaning | Comes from |
|---|---|---|
| `sales_order_id` | Primary key | header |
| `sales_order_number` | Business key, e.g. `SO43659` | header |
| `order_date_key` | yyyymmdd integer, joins to `dim_date.date_key` | header `order_date` |
| `order_date` | Order date as a DATE | header `order_date` |
| `customer_id` | Joins to `dim_customer` | header |
| `territory_id` | Joins to `dim_territory` | header |
| `sales_person_id` | Sales rep; NULL for online orders | header |
| `channel` | `'online'` or `'reseller'` | derived from header `online_order_flag` |
| `revenue` | **= `sub_total`** (settled decision: excludes tax and freight) | header |
| `tax_amt`, `freight`, `total_due` | Kept alongside so revenue can be reconciled to what was billed | header |
| `line_count` | Number of order lines | aggregated from lines |
| `units` | Sum of `order_qty` over the order's lines | aggregated from lines |

## Tests it needs

1. `unique` and `not_null` on `sales_order_id`.
2. `not_null` and `accepted_values` (`online`, `reseller`) on `channel`.
3. `relationships` from `customer_id` to `dim_customer`, `territory_id` to `dim_territory` and
   `order_date_key` to `dim_date`. Copy the shape from `fct_sales_lines` in `_marts.yml`.
4. `not_null` on `revenue`.
5. A singular test that order revenue reconciles to line revenue: for each order,
   `fct_orders.revenue` matches the sum of `fct_sales_lines.revenue` within 0.01. Use the existing
   reconciliation test as a model.
6. A singular test for the channel rule from profiling: channels never overlap, so every `online` order
   belongs to an `individual` customer and every `reseller` order to a `store` (`dim_customer.customer_type`).
   It returns the orders that break the rule.

## Hints

- **Start from the header, not the lines.** The header is already at the grain you want. Pick the
  columns and rename where the table above says so.
- **Channel** is a `case` expression on `online_order_flag`. Decide what should happen if the flag is
  NULL. (Test 2 tells you if it ever is.)
- **Line count and units need the lines, and that is where the trap is.** Joining the header straight to
  `stg_sales_order_detail` turns one row per order into one row per line (fan-out). Then `revenue`
  would be counted once per line. Aggregate the lines to one row per `sales_order_id` in a CTE first,
  then join that CTE to the header.
- **Which join?** Think about what should happen to an order with no lines. The reconciliation test in
  `tests/` already treats that as an error, so either choice is caught. Pick one and say why in a comment.
- **Dates:** `fct_sales_lines.sql` already builds `order_date_key` and `order_date` from a timestamp.
  Reuse the same expressions so the two facts always agree.
- Refer to other models with `{{ ref('...') }}`, never with a hard-coded table name. That is how dbt
  builds the lineage graph and runs things in the right order.

## Check your work

From `dbt/`, with the environment variables from the PR description set:

```bash
dbt compile --select fct_orders
```

This prints the SQL dbt will run, with `ref()` resolved. It is the fastest way to catch typos.

```bash
dbt build --select fct_orders+
```

This builds `fct_orders` and runs its tests plus anything downstream of it.

Expected results on the current export:

- 31,465 rows; 27,659 `online` and 3,806 `reseller`.
- `sum(revenue)` is about 109,846,381.40. It equals `sum(sub_total)` in `stg_sales_order_header` and is
  within a fraction of a cent of `sum(revenue)` in `fct_sales_lines`. The lines carry 6 decimals, the
  header 4.
- Every test passes.

## Done when

- [x] `fct_orders.sql` written, with a header comment stating the grain and the revenue definition
- [x] Columns documented and tests 1 to 4 added in `_marts.yml`
- [x] Singular tests 5 and 6 added in `dbt/tests/`
- [x] `dbt build` green locally, then in the `aw_medallion` job on Databricks
