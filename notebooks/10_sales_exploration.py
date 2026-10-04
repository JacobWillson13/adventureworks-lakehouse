# Databricks notebook source
# MAGIC %md
# MAGIC # 10 · Sales exploration on gold
# MAGIC Rebuilds part 1 of `00_local_prototype.ipynb` on the gold layer: category revenue, AOV by territory
# MAGIC within each channel, monthly trends, the July 2013 catalog launch and reseller batching.
# MAGIC Revenue = `sub_total`; analysis window May 2011 to May 2014. Logic lives in `awlake.analysis.sales`.
# MAGIC
# MAGIC Runs on Databricks as a task of the `aw_analysis` job, or locally as a script after
# MAGIC `dbt build --target local` (`python notebooks/10_sales_exploration.py`).

# COMMAND ----------

import sys
from pathlib import Path

root = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "config" / "aw_schema.json").exists())
sys.path.insert(0, str(root / "src"))

from awlake.analysis import plots, sales  # noqa: E402
from awlake.analysis.runtime import notebook_context, read_gold, show  # noqa: E402

ctx = notebook_context(globals(), catalog="workspace", figures_dir="")
G = globals()

# COMMAND ----------

pm = read_gold(ctx, "mart_product_monthly")
cm = read_gold(ctx, "mart_channel_monthly")
orders = ctx.spark.sql(f"""
    SELECT o.sales_order_id, o.channel, o.revenue, t.territory_name, t.territory_group
    FROM {ctx.gold}.fct_orders o
    JOIN {ctx.gold}.dim_date d ON d.date_key = o.order_date_key
    JOIN {ctx.gold}.dim_territory t ON t.territory_id = o.territory_id
    WHERE d.is_in_analysis_window
""").toPandas().astype({"revenue": float})
print(f"{len(orders):,} orders in the window, revenue ${orders.revenue.sum():,.0f}")

# COMMAND ----------

# MAGIC %md ## Revenue by category

# COMMAND ----------

cat = sales.category_revenue(pm)
show(G, cat)
plots.save(plots.category_revenue(cat), ctx.figures_dir, "sales_category_revenue.png")

# COMMAND ----------

# MAGIC %md ## Average order value by territory: channel mix first, then within each channel

# COMMAND ----------

terr = sales.territory_aov(orders)
show(G, terr)
print(f"Correlation of reseller order share with overall AOV: r = {sales.channel_mix_correlation(terr):.2f}")
plots.save(plots.territory_aov(terr), ctx.figures_dir, "sales_territory_aov_by_channel.png")

# COMMAND ----------

# MAGIC %md ## Monthly trends, reseller batching and the July 2013 break

# COMMAND ----------

batches = sales.reseller_batching(cm)
show(G, batches)
fig = plots.monthly_trends(sales.monthly_pivot(cm, "revenue"), sales.monthly_pivot(cm, "orders"),
                           batches.month_start_date)
plots.save(fig, ctx.figures_dir, "sales_monthly_trends.png")
show(G, sales.yearly_summary(cm))
show(G, sales.reseller_month_of_year(cm))
show(G, sales.catalog_launch(pm))
