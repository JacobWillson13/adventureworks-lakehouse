# Databricks notebook source
# MAGIC %md
# MAGIC # 12 · Monthly unit forecasts on gold
# MAGIC Target: monthly units per product from `mart_product_monthly` (both channels); revenue alongside at the
# MAGIC recent average price. Top 5 products are chosen on pre-backtest units only. Candidates: naive baselines,
# MAGIC ETS, ETS after the July 2013 break, and a channel split (online and reseller separately, since reseller
# MAGIC orders arrive in monthly batches with empty months). Rolling-origin backtest over Dec 2013 to May 2014,
# MAGIC error = WAPE; each product's best model forecasts Jun to Aug 2014. Logic in `awlake.analysis.forecasting`.
# MAGIC Tracked in MLflow: parameters, WAPE per model, the forecast model and figures.

# COMMAND ----------

import sys
from pathlib import Path

root = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "config" / "aw_schema.json").exists())
sys.path.insert(0, str(root / "src"))

import mlflow  # noqa: E402
import pandas as pd  # noqa: E402

from awlake.analysis import BREAK, plots, tracking  # noqa: E402
from awlake.analysis import forecasting as fc  # noqa: E402
from awlake.analysis.runtime import notebook_context, read_gold, show  # noqa: E402

ctx = notebook_context(globals(), catalog="workspace", experiment_id="", figures_dir="")
G = globals()
tracking.set_experiment(ctx)

# COMMAND ----------

pm = read_gold(ctx, "mart_product_monthly")
top = fc.select_top_products(pm)
show(G, top)

# COMMAND ----------

# MAGIC %md ## Backtest and forecast

# COMMAND ----------

res = fc.forecast_top_products(pm, top)
names = res["names"]
show(G, res["scores"].round(3))
show(G, res["wape_by_product"].rename(index=names).round(3))
show(G, res["forecast"].round(1))

# COMMAND ----------

# MAGIC %md ## Diagnostics: trend, seasonality, change points

# COMMAND ----------

strength, stl = fc.stl_strength(res["series"].sum(axis=1))
print(strength)
cps = fc.change_points(res["series"], names)
show(G, cps)

# COMMAND ----------

# MAGIC %md ## Figures and MLflow run

# COMMAND ----------

series = res["series"]
figs = [
    plots.save(plots.top_products(series, names, fc.TEST_START), ctx.figures_dir, "forecast_top_products_units.png"),
    plots.save(plots.stl_components(series.sum(axis=1), stl), ctx.figures_dir, "forecast_stl_decomposition.png"),
    plots.save(plots.backtest_wape(res["scores"]), ctx.figures_dir, "forecast_backtest_wape.png"),
    plots.save(plots.forecasts(series, res["forecast"], names), ctx.figures_dir, "forecast_jun_aug_2014.png"),
]

with mlflow.start_run(run_name="product_forecasting") as run:
    mlflow.log_params({"target": "monthly units per product", "top_n": fc.TOP_N, "min_coverage": fc.MIN_COVERAGE,
                       "test_start": fc.TEST_START.date().isoformat(), "horizon": fc.H,
                       "origins": ",".join(o.strftime("%Y-%m") for o in fc.ORIGINS),
                       "break": BREAK.date().isoformat(), "models": ",".join(res["scores"].index),
                       "products": ",".join(str(p) for p in top.product_id),
                       "source": "aw_gold.mart_product_monthly"})
    for model, r in res["scores"].iterrows():
        key = model.lower().replace(" ", "_").replace("(", "").replace(")", "").replace(",", "")
        mlflow.log_metrics({f"wape_{key}": r.WAPE, f"mae_{key}": r.MAE})
    mlflow.log_metrics({"wape_selected_models": res["selected_wape"], "wape_best_overall": res["scores"].WAPE.min(),
                        "wape_naive": res["scores"].loc["Naive", "WAPE"], **strength})
    tracking.log_table(res["backtest"], "tables/backtest.csv")
    tracking.log_table(res["forecast"], "tables/forecast_jun_aug_2014.csv")
    tracking.log_table(cps, "tables/change_points.csv")
    tracking.log_figures(figs)
    mlflow.pyfunc.log_model(name="product_forecast", python_model=tracking.forecaster_model()(res["forecast"]),
                            input_example=pd.DataFrame({"product_id": top.product_id.head(1).astype("int64"), "horizon": [fc.H]}))
    print("MLflow run", run.info.run_id)
