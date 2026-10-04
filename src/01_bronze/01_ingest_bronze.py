# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Bronze ingestion
# MAGIC Loads every raw AdventureWorks file from the landing volume into `aw_bronze`.
# MAGIC
# MAGIC - The source CSVs have **no header row**; column names come from Microsoft's DDL via `config/aw_schema.json`.
# MAGIC - All columns land as **STRING**. Typing happens in silver.
# MAGIC - File-specific fixes (encoding, broken rows, exclusions) live in `config/ingest_overrides.json`, not in code.
# MAGIC - Each table's row count is checked against `config/expected_row_counts.json`; any mismatch fails the run.

# COMMAND ----------

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Notebook cwd is its own folder; walk up to the repo root and make src/ importable.
root = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "config" / "aw_schema.json").exists())
sys.path.insert(0, str(root / "src"))

from awlake.bronze import add_lineage, read_source  # noqa: E402
from awlake.config import Config  # noqa: E402

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
catalog = dbutils.widgets.get("catalog")
landing = f"/Volumes/{catalog}/aw_raw/landing"
bronze = f"`{catalog}`.`aw_bronze`"
run_id = str(uuid.uuid4())

cfg = Config(root)
files = sorted(f for f in os.listdir(landing) if f.lower().endswith(".csv"))
print(f"run_id={run_id}  files={len(files)}  landing={landing}")

# COMMAND ----------

results = []
for fname in files:
    stem = fname[:-4]
    spec = cfg.spec(stem)
    rec = {"file": fname, "bronze_table": spec.bronze_table, "expected_rows": spec.expected_rows,
           "rows": None, "status": None, "note": spec.note}
    if spec.exclude:
        rec["status"] = "excluded"
        results.append(rec)
        continue

    df = add_lineage(read_source(spark, f"{landing}/{fname}", spec), fname, run_id)
    (df.write.mode("overwrite").option("overwriteSchema", "true")
       .saveAsTable(f"{bronze}.`{spec.bronze_table}`"))

    n = spark.table(f"{bronze}.`{spec.bronze_table}`").count()
    rec["rows"] = n
    rec["status"] = "ok" if spec.expected_rows is None or n == spec.expected_rows else "ROW_COUNT_MISMATCH"
    results.append(rec)
    print(f"{rec['status']:>18}  {spec.bronze_table:45} {n:>8}")

# COMMAND ----------

# Audit log: one row per file per run.
audit = spark.createDataFrame(
    [{**r, "run_id": run_id, "logged_at": datetime.now(timezone.utc).isoformat()} for r in results],
    "file string, bronze_table string, expected_rows long, rows long, status string, note string, run_id string, logged_at string",
)
audit.write.mode("append").saveAsTable(f"{bronze}.`ingest_audit`")
display(audit.orderBy("status", "file"))

# COMMAND ----------

unknown = [f for f in files if f[:-4] not in cfg.expected_rows and not cfg.spec(f[:-4]).exclude]
bad = [r for r in results if r["status"] == "ROW_COUNT_MISMATCH"]
if unknown or bad:
    raise RuntimeError(f"Bronze validation failed. Row-count mismatches: {bad}. Files with no expected count: {unknown}")
print(f"Bronze OK: {sum(r['status'] == 'ok' for r in results)} tables loaded, "
      f"{sum(r['status'] == 'excluded' for r in results)} excluded.")
