"""Run every raw file through the bronze reader with local Spark and check row counts.

Same code path as src/01_bronze/01_ingest_bronze.py, minus the Delta writes.
Needs Java 17+ and `pip install pyspark`.

Usage (from repo root):
    python scripts/bronze_dryrun.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pyspark.sql import SparkSession  # noqa: E402

from awlake.bronze import read_source  # noqa: E402
from awlake.config import Config  # noqa: E402


def main() -> int:
    cfg = Config(ROOT)
    raw = ROOT / "data" / "raw"
    spark = (SparkSession.builder.master("local[*]").appName("aw-bronze-dryrun")
             .config("spark.ui.enabled", "false").getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")

    failures = 0
    for f in sorted(raw.glob("*.csv")):
        spec = cfg.spec(f.stem)
        if spec.exclude:
            print(f"{'excluded':>10}  {f.name}")
            continue
        try:
            n = read_source(spark, str(f), spec).count()
            status = "ok" if n == spec.expected_rows else f"MISMATCH (expected {spec.expected_rows})"
        except Exception as e:  # noqa: BLE001
            n, status = -1, f"ERROR {type(e).__name__}: {str(e).splitlines()[0][:120]}"
        failures += status != "ok"
        print(f"{status:>10}  {spec.bronze_table:45} {n:>8}")

    spark.stop()
    print(f"\n{'PASS' if not failures else f'FAIL: {failures} file(s)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
