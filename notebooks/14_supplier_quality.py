# Databricks notebook source
# MAGIC %md
# MAGIC # 14 · Supplier quality
# MAGIC Received vs rejected quantities by vendor and over time from `mart_vendor_quality`, over every
# MAGIC purchase order (Apr 2011 to Sep 2014). The sales analysis window does not apply: it exists because the sales
# MAGIC extract is truncated, and the purchasing data is not.
# MAGIC Rejections split into whole deliveries refused (purchase orders with status rejected) and partial
# MAGIC rejections at receipt. Lead time: the source has no receipt date, so only planned (due date - order date)
# MAGIC and declared (product_vendor) lead times exist; the check below shows whether they vary enough to analyze.
# MAGIC Logic in `awlake.analysis.supplier`.

# COMMAND ----------

import sys
from pathlib import Path

root = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "config" / "aw_schema.json").exists())
sys.path.insert(0, str(root / "src"))

from awlake.analysis import plots, supplier  # noqa: E402
from awlake.analysis.runtime import notebook_context, read_gold, show  # noqa: E402

ctx = notebook_context(globals(), catalog="workspace", figures_dir="")
G = globals()

# COMMAND ----------

vq = read_gold(ctx, "mart_vendor_quality")
lines = read_gold(ctx, "fct_purchase_lines")
print(supplier.overall(vq))
summary = supplier.vendor_summary(vq)
worst = supplier.worst_vendors(summary)
show(G, worst)
show(G, supplier.by_credit_rating(summary))
print("Lead time support:", supplier.lead_time_support(lines))

# COMMAND ----------

monthly = supplier.monthly_quality(vq)
plots.save(plots.worst_vendors(worst), ctx.figures_dir, "supplier_worst_vendors.png")
plots.save(plots.rejection_over_time(monthly), ctx.figures_dir, "supplier_rejection_over_time.png")
