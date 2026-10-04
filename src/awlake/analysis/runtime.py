"""Notebook plumbing that works the same on Databricks and on local Spark.

On Databricks the notebook passes its globals: `spark` and `dbutils` exist, parameters come from job
widgets and gold lives in `<catalog>.aw_gold`. Run as a plain Python script locally, there is no
`dbutils`: parameters come from AW_<NAME> environment variables, Spark is awlake.local_spark (gold
built by `dbt build --target local`) and MLflow logs to <repo>/.lakehouse/mlflow.db.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pandas as pd

from ..config import find_repo_root


@dataclass
class Context:
    spark: object
    params: dict
    root: Path
    on_databricks: bool

    @property
    def gold(self) -> str:
        catalog = self.params.get("catalog", "")
        return f"`{catalog}`.aw_gold" if self.on_databricks and catalog else "aw_gold"

    @property
    def figures_dir(self) -> Path:
        d = Path(self.params.get("figures_dir") or self.root / "reports" / "figures")
        d.mkdir(parents=True, exist_ok=True)
        return d


def notebook_context(g: dict, **defaults: str) -> Context:
    """Spark session and parameters for a notebook. `g` is the notebook's globals()."""
    dbutils = g.get("dbutils")
    spark = g.get("spark")
    root = find_repo_root()
    params = {}
    for name, default in defaults.items():
        if dbutils is not None:
            dbutils.widgets.text(name, default)
            params[name] = dbutils.widgets.get(name)
        else:
            params[name] = os.environ.get(f"AW_{name.upper()}", default)
    if spark is None:
        from ..local_spark import local_session
        spark = local_session("aw-analysis")
    return Context(spark=spark, params=params, root=root, on_databricks=dbutils is not None)


def read_gold(ctx: Context, table: str, where: str | None = None) -> pd.DataFrame:
    """One gold table as pandas. Gold marts are small (the largest analysis input is ~31k orders)."""
    sql = f"SELECT * FROM {ctx.gold}.{table}" + (f" WHERE {where}" if where else "")
    df = ctx.spark.sql(sql).toPandas()
    for c in df.columns:
        if c.endswith("_date") or c == "month_start_date":
            df[c] = pd.to_datetime(df[c])
        elif df[c].dtype == object and isinstance(next(iter(df[c].dropna()), None), Decimal):
            df[c] = df[c].astype(float)
    return df


def show(g: dict, df: pd.DataFrame) -> None:
    """display() in a Databricks notebook, print locally."""
    if "display" in g and g.get("dbutils") is not None:
        g["display"](df)
    else:
        with pd.option_context("display.width", 160, "display.max_columns", 20):
            print(df.to_string(max_rows=40))
