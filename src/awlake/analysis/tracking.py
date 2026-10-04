"""MLflow tracking for the clustering and forecasting notebooks.

On Databricks the experiment is the bundle resource `aw_analysis` (resources/aw_analysis.yml); the job
passes its ID. Locally, runs go to <repo>/.lakehouse/mlflow.db (artifacts in .lakehouse/mlartifacts) unless
MLFLOW_TRACKING_URI is set; browse them with `mlflow ui --backend-store-uri sqlite:///.lakehouse/mlflow.db`.
mlflow is imported inside the functions so the analysis modules and tests do not need it.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd

LOCAL_EXPERIMENT = "aw_analysis"


def set_experiment(ctx) -> str:
    """Point MLflow at the job's experiment (Databricks) or a local store. Returns the experiment ID."""
    import mlflow

    experiment_id = ctx.params.get("experiment_id", "")
    if ctx.on_databricks and experiment_id:
        return mlflow.set_experiment(experiment_id=experiment_id).experiment_id
    if not ctx.on_databricks and not os.environ.get("MLFLOW_TRACKING_URI"):
        store = ctx.root / ".lakehouse"
        store.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(f"sqlite:///{store / 'mlflow.db'}")
        if mlflow.get_experiment_by_name(LOCAL_EXPERIMENT) is None:
            # Artifacts next to the store, not in ./mlruns of whatever directory the script runs from.
            mlflow.create_experiment(LOCAL_EXPERIMENT, artifact_location=(store / "mlartifacts").as_uri())
    return mlflow.set_experiment(LOCAL_EXPERIMENT).experiment_id


def log_table(df: pd.DataFrame, artifact_file: str) -> None:
    """A DataFrame as a CSV artifact."""
    import mlflow

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / Path(artifact_file).name
        df.to_csv(path, index=False)
        mlflow.log_artifact(str(path), artifact_path=str(Path(artifact_file).parent) or None)


def log_figures(paths) -> None:
    import mlflow

    for p in paths:
        mlflow.log_artifact(str(p), artifact_path="figures")


def log_metrics(metrics: dict, prefix: str = "") -> None:
    import mlflow

    mlflow.log_metrics({f"{prefix}{k}": float(v) for k, v in metrics.items()})


def forecaster_model():
    """An MLflow pyfunc wrapping the per-product forecasts: input rows (product_id, horizon) and the
    output is the forecast table for those products up to that horizon. The point forecasts and
    intervals are computed at training time (they come from models refit on all history), so loading
    the model needs no statsmodels."""
    import mlflow.pyfunc

    class ProductForecast(mlflow.pyfunc.PythonModel):
        def __init__(self, forecast: pd.DataFrame):
            self.forecast = forecast.assign(horizon=forecast.groupby("product_id").cumcount() + 1)

        def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
            out = []
            for r in model_input.itertuples():
                f = self.forecast[(self.forecast.product_id == r.product_id) & (self.forecast.horizon <= r.horizon)]
                out.append(f)
            return pd.concat(out, ignore_index=True) if out else self.forecast.iloc[0:0]

    return ProductForecast
