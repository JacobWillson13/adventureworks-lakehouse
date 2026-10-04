# Databricks notebook source
# MAGIC %md
# MAGIC # 11 · Customer segmentation on gold
# MAGIC Individual (online) customers are clustered with K-means on RFM-style features from
# MAGIC `mart_customer_features`; reseller stores are profiled separately from `mart_store_profile`
# MAGIC (they are a different population: about $21k per order vs about $1k). k is chosen by a fixed rule
# MAGIC (stable, no tiny cluster, best silhouette in 3 to 6). Logic in `awlake.analysis.segmentation`.
# MAGIC The run is tracked in MLflow: parameters, quality metrics, cluster sizes, the fitted pipeline and figures.

# COMMAND ----------

import sys
from pathlib import Path

root = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "config" / "aw_schema.json").exists())
sys.path.insert(0, str(root / "src"))

import mlflow  # noqa: E402

from awlake.analysis import SEED, plots, segmentation, tracking  # noqa: E402
from awlake.analysis.runtime import notebook_context, read_gold, show  # noqa: E402

ctx = notebook_context(globals(), catalog="workspace", experiment_id="", figures_dir="")
G = globals()
tracking.set_experiment(ctx)

# COMMAND ----------

feat = read_gold(ctx, "mart_customer_features").set_index("customer_id")
stores = read_gold(ctx, "mart_store_profile")
print(f"{len(feat):,} individual customers, {len(stores):,} reseller stores")

# COMMAND ----------

# MAGIC %md ## Individuals: choose k, fit, profile

# COMMAND ----------

seg = segmentation.segment_customers(feat, seed=SEED)
show(G, seg["k_table"].round(3))
print("Chosen k =", seg["k"])
show(G, seg["profiles"])
show(G, seg["redundancy"].round(3))

# COMMAND ----------

# MAGIC %md ## Reseller stores: value tiers and lapsed accounts

# COMMAND ----------

store_tiers, store_summary = segmentation.profile_stores(stores)
tier_table = segmentation.store_tier_table(store_tiers)
show(G, tier_table)
print(store_summary)

# COMMAND ----------

# MAGIC %md ## Figures and MLflow run

# COMMAND ----------

figs = [
    plots.save(plots.k_selection(seg["k_table"], seg["k"]), ctx.figures_dir, "segmentation_k_selection.png"),
    plots.save(plots.segments(seg["profiles"], feat, seg["labels"]), ctx.figures_dir, "segmentation_segments.png"),
    plots.save(plots.store_tiers(tier_table), ctx.figures_dir, "segmentation_store_tiers.png"),
]

with mlflow.start_run(run_name="customer_segmentation") as run:
    mlflow.log_params({"model": "kmeans", "features": ",".join(segmentation.FEATURES),
                       "log_features": ",".join(segmentation.LOG_COLS), "k_range": "2-8", "k_rule":
                       "k in 3..6, stability ARI >= 0.9, min cluster share >= 3%, best silhouette",
                       "n_init": 10, "seed": SEED, "source": "aw_gold.mart_customer_features"})
    tracking.log_metrics(seg["metrics"])
    for r in seg["profiles"].itertuples():
        mlflow.log_metric(f"cluster_size_{r.cluster}", r.customers)
        mlflow.log_metric(f"cluster_revenue_share_{r.cluster}", r.revenue_share)
    for r in seg["redundancy"].itertuples():
        mlflow.log_metric("ari_" + r.variant.split(" (")[0].replace(" ", "_"), r.ari_vs_full)
    tracking.log_metrics(store_summary, prefix="stores_")
    tracking.log_table(seg["k_table"], "tables/k_selection.csv")
    tracking.log_table(seg["profiles"], "tables/cluster_profiles.csv")
    tracking.log_table(tier_table, "tables/store_tiers.csv")
    tracking.log_figures(figs)
    mlflow.sklearn.log_model(seg["pipeline"], name="kmeans_pipeline",
                             input_example=feat[segmentation.FEATURES].head(5).astype(float))
    print("MLflow run", run.info.run_id)
