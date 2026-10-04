"""Run src/02_silver/sales.py on local Spark and evaluate its expectations against the real export.

Raw files go through the bronze reader into global temp views; sales.py runs unchanged against them, with
a stand-in for the `dp` decorators that records each dataset and its expectations. For each dataset this
prints the input rows, every expectation's violation count and severity, and the rows a pipeline update
would keep. Open-source pyspark.pipelines has no expectations, hence the stand-in.
Needs Java 17+ and `pip install pyspark`.

Usage (from repo root):
    python scripts/silver_dryrun.py
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

from awlake.bronze import add_lineage, read_source  # noqa: E402
from awlake.config import Config  # noqa: E402

SEVERITY = {"expect": "warn", "expect_or_drop": "drop", "expect_or_fail": "fail"}


def recording_dp(datasets: list):
    """Minimal stand-in for `pyspark.pipelines` covering what sales.py uses."""
    dp = types.ModuleType("pyspark.pipelines")

    def expectation(kind):
        def deco_factory(name, condition):
            def deco(fn):
                fn.__dict__.setdefault("_expectations", []).insert(0, (name, condition, SEVERITY[kind]))
                return fn
            return deco
        return deco_factory

    for kind in SEVERITY:
        setattr(dp, kind, expectation(kind))

    def materialized_view(name=None, comment=None, **_):
        def deco(fn):
            datasets.append((name or fn.__name__, fn))
            return fn
        return deco

    dp.materialized_view = materialized_view
    return dp


def main() -> int:
    cfg = Config(ROOT)
    raw = ROOT / "data" / "raw"
    spark = (SparkSession.builder.master("local[*]").appName("aw-silver-dryrun")
             .config("spark.ui.enabled", "false")
             .config("spark.sql.ansi.enabled", "true")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")

    for f in sorted(raw.glob("*.csv")):
        spec = cfg.spec(f.stem)
        if not spec.exclude:
            add_lineage(read_source(spark, str(f), spec), f.name, "dryrun").createOrReplaceGlobalTempView(
                spec.bronze_table)
    spark.conf.set("bronze_schema", "global_temp")

    datasets: list = []
    import pyspark
    pyspark.pipelines = sys.modules["pyspark.pipelines"] = recording_dp(datasets)
    source = ROOT / "src" / "02_silver" / "sales.py"
    exec(compile(source.read_text(), str(source), "exec"), {"spark": spark, "__name__": "sales"})

    failures = 0
    for name, fn in datasets:
        df = fn().cache()
        exps = getattr(fn, "_expectations", [])
        # An expectation passes when its condition is true; NULL counts as a violation (conservative).
        counts = df.select(
            F.count(F.lit(1)).alias("__rows"),
            *[F.sum(F.when(F.expr(cond), 0).otherwise(1)).alias(n) for n, cond, _ in exps],
        ).collect()[0]
        drop = [cond for _, cond, sev in exps if sev == "drop"]
        kept = df.filter(" AND ".join(f"COALESCE({c}, false)" for c in drop)).count() if drop else counts["__rows"]
        print(f"\n{name}: {counts['__rows']} rows in, {kept} kept")
        for n, _, sev in exps:
            failures += sev == "fail" and counts[n] > 0
            print(f"    {sev:>4}  {n:40} {counts[n]:>7} violations")
        df.unpersist()

    spark.stop()
    print(f"\n{len(datasets)} datasets. {'PASS' if not failures else f'FAIL: {failures} fail-level violation(s)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
