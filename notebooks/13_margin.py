# Databricks notebook source
# MAGIC %md
# MAGIC # 13 · Margin over time
# MAGIC Gross margin = revenue - order_qty x the product's standard cost **on the order date**: product cost history
# MAGIC is joined to order lines by effective date in `fct_sales_line_margin` (start_date <= order date <= end_date,
# MAGIC open-ended end_date = current). 64 reseller lines fall after their product's last cost period and carry
# MAGIC the latest earlier cost forward (dbt test `assert_sales_lines_have_effective_cost_row` lists them).
# MAGIC Input: `mart_margin_monthly`. Logic in `awlake.analysis.margin`.

# COMMAND ----------

import sys
from pathlib import Path

root = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "config" / "aw_schema.json").exists())
sys.path.insert(0, str(root / "src"))

from awlake.analysis import margin, plots  # noqa: E402
from awlake.analysis.runtime import notebook_context, read_gold, show  # noqa: E402

ctx = notebook_context(globals(), catalog="workspace", figures_dir="")
G = globals()

# COMMAND ----------

mm = read_gold(ctx, "mart_margin_monthly")
monthly = margin.monthly_margin(mm)
print(margin.margin_range(monthly))
show(G, margin.margin_by(mm, "category_name"))
show(G, margin.margin_by(mm, "channel"))
show(G, margin.negative_margin_months(mm, "channel"))
print(f"Lines with carried-forward cost in the window: {int(mm.lines_cost_carried_forward.sum())}")

# COMMAND ----------

fig = plots.margin_over_time(monthly, margin.monthly_margin_pct(mm, "category_name"),
                             margin.monthly_margin_pct(mm, "channel"))
plots.save(fig, ctx.figures_dir, "margin_over_time.png")
