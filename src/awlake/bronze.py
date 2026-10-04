"""Spark readers for the bronze layer. Every source column lands as STRING;
typing happens in silver, so parse problems never block ingestion silently."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

from .config import SourceSpec
from .repair import rejoin_rows


# Charsets Spark 4's CSV reader accepts. Anything else (e.g. windows-1252) is decoded in Python.
SPARK_CHARSETS = {"utf-8", "us-ascii", "iso-8859-1", "utf-16", "utf-16be", "utf-16le", "utf-32"}


def parse_text_csv(text: str, n_cols: int, sep: str = "\t", quote: str = '"') -> list[list[str | None]]:
    """Python-side CSV parse with the same dialect as the Spark path. Raises on a wrong field count."""
    rows = []
    for i, r in enumerate(csv.reader(io.StringIO(text, newline=""), delimiter=sep, quotechar=quote)):
        if len(r) != n_cols:
            raise ValueError(f"row {i} has {len(r)} fields, expected {n_cols}")
        rows.append([f if f != "" else None for f in r])
    return rows


def string_schema(columns: list[str]) -> StructType:
    return StructType([StructField(c, StringType(), True) for c in columns])


def read_source(spark: SparkSession, path: str, spec: SourceSpec) -> DataFrame:
    """Read one raw file according to its SourceSpec. `path` must be readable by
    both Spark and Python's open() (true for local paths and /Volumes/... paths)."""
    schema = string_schema(spec.bronze_columns)

    if Path(path).stat().st_size == 0:
        return spark.createDataFrame([], schema)

    o = spec.read_options
    if spec.reader == "rejoin_rows":
        text = Path(path).read_bytes().decode(o["encoding"])
        return spark.createDataFrame(rejoin_rows(text, len(spec.columns), sep=o["sep"]), schema)

    if o["encoding"].lower() not in SPARK_CHARSETS:
        # Strict decode: an undefined byte raises instead of becoming U+FFFD.
        text = Path(path).read_bytes().decode(o["encoding"])
        return spark.createDataFrame(parse_text_csv(text, len(spec.columns), o["sep"], o["quote"]), schema)

    df = (
        spark.read.schema(schema)
        .option("sep", o["sep"])
        .option("quote", o["quote"])
        .option("escape", o["escape"])
        .option("encoding", o["encoding"])
        .option("multiLine", o["multiLine"])
        .option("header", False)
        .option("mode", "FAILFAST")  # wrong field count -> job fails, never silently nulls
        .csv(path)
    )
    # Guard against a stray CR on the last field if line-ending detection misses.
    last = spec.bronze_columns[-1]
    return df.withColumn(last, F.regexp_replace(F.col(last), "\r$", ""))


def add_lineage(df: DataFrame, source_file: str, run_id: str) -> DataFrame:
    return (
        df.withColumn("_source_file", F.lit(source_file))
        .withColumn("_ingest_run_id", F.lit(run_id))
        .withColumn("_ingested_at", F.current_timestamp())
    )
