"""A local Spark session with a persistent catalog, so silver, dbt and the analyses can run end to end
on one machine.

Tables live in `<lakehouse>/warehouse` and the catalog (a Derby metastore) in `<lakehouse>/metastore_db`,
default `<repo>/.lakehouse` (gitignored). scripts/silver_dryrun.py --write fills `aw_silver`, the dbt
`local` target (dbt/profiles.yml) builds `aw_gold` with the same settings, and scripts/analysis_local.py
reads gold back. Not used on Databricks, where Unity Catalog plays this role.
"""
from __future__ import annotations

import os
from pathlib import Path

from .config import find_repo_root


def lakehouse_dir(root: Path | None = None) -> Path:
    """AW_LOCAL_LAKEHOUSE if set, else <repo>/.lakehouse."""
    env = os.environ.get("AW_LOCAL_LAKEHOUSE")
    return Path(env).resolve() if env else (root or find_repo_root()) / ".lakehouse"


def local_conf(lakehouse: Path) -> dict[str, str]:
    """Spark settings shared by every local process (dbt reads the same values from profiles.yml)."""
    return {
        "spark.sql.warehouse.dir": str(lakehouse / "warehouse"),
        "spark.hadoop.javax.jdo.option.ConnectionURL":
            f"jdbc:derby:;databaseName={lakehouse / 'metastore_db'};create=true",
        "spark.sql.ansi.enabled": "true",           # Databricks default
        "spark.sql.session.timeZone": "UTC",
        "spark.ui.enabled": "false",
        "spark.driver.extraJavaOptions": f"-Dderby.system.home={lakehouse}",   # derby.log goes here, not cwd
    }


def local_session(app: str = "aw-local", lakehouse: Path | None = None):
    from pyspark.sql import SparkSession

    lakehouse = lakehouse or lakehouse_dir()
    lakehouse.mkdir(parents=True, exist_ok=True)
    builder = SparkSession.builder.master("local[*]").appName(app).enableHiveSupport()
    for k, v in local_conf(lakehouse).items():
        builder = builder.config(k, v)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark
