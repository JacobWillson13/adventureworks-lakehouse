"""Typed select lists for silver, built from config/aw_schema.json.

Bronze holds every source column as STRING under its PascalCase source name. typed_columns() turns one
schema table into the list of Column expressions that casts, cleans and snake_cases it, so each silver
dataset is `bronze.select(*typed_columns("SalesOrderHeader"))` plus its expectations.

Casting never raises: a value that cannot be parsed becomes NULL, and the pipeline's expectations decide
what happens to that row. Pure column expressions, so the same code runs in the pipeline and in local tests.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pyspark.sql import Column
from pyspark.sql import functions as F

from .config import find_repo_root, safe_column, to_snake

LINEAGE = ["_source_file", "_ingest_run_id", "_ingested_at"]

# Types with no useful scalar form yet. XML is parsed later if an analysis needs it; the binary and
# spatial types are photos, hierarchy paths and map points that nothing downstream uses.
SKIPPED_SQL_TYPES = ("xml", "varbinary", "hierarchyid", "geography")

# Person is promoted with its key, type and name columns only; contact details and survey XML stay in bronze.
PERSON_NAME_COLUMNS = ["BusinessEntityID", "PersonType", "Title", "FirstName", "MiddleName", "LastName", "Suffix", "ModifiedDate"]


@lru_cache(maxsize=1)
def _schema() -> dict:
    # Resolve from this file, not the cwd: the pipeline runs with a different working directory.
    root = find_repo_root(Path(__file__).resolve().parent)
    return json.loads((root / "config" / "aw_schema.json").read_text())


def is_skipped(column: dict) -> bool:
    return column["sql_type"].lower().startswith(SKIPPED_SQL_TYPES)


def cast_column(column: dict) -> Column:
    """Expression that types one bronze STRING column according to its aw_schema.json entry."""
    c = F.col(safe_column(column["name"]))
    sql_type = column["sql_type"].lower()
    spark_type = column["spark_type"].upper()

    if sql_type == "uniqueidentifier":
        # Some tables wrap GUIDs in {braces}; normalize to bare upper-case.
        return F.upper(F.regexp_replace(c, r"[{}]", ""))
    if spark_type == "TIMESTAMP":
        # Bronze timestamps look like '2011-05-31 00:00:00' or '2014-09-12 11:15:07.263000000'.
        # Spark keeps microseconds, so trim to 26 characters before parsing.
        return F.try_to_timestamp(F.substring(c, 1, 26))
    if spark_type == "DATE":
        return F.substring(c, 1, 10).try_cast("date")
    if spark_type == "BOOLEAN":
        # SQL Server bit exports as 0/1. Anything else becomes NULL rather than a silent False.
        return F.when(c == "1", F.lit(True)).when(c == "0", F.lit(False))
    if spark_type == "STRING":
        return c
    return c.try_cast(spark_type)


def typed_columns(schema_table: str, include: list[str] | None = None) -> list[Column]:
    """Select list for one table: typed, snake_case source columns followed by the bronze lineage columns.

    `include` limits the output to these source column names (in schema order). XML, varbinary,
    hierarchyid and geography columns are always skipped.
    """
    columns = _schema()[schema_table]["columns"]
    if include is not None:
        unknown = set(include) - {c["name"] for c in columns}
        if unknown:
            raise KeyError(f"{schema_table} has no column(s) {sorted(unknown)}")
        columns = [c for c in columns if c["name"] in include]
    typed = [cast_column(c).alias(to_snake(c["name"])) for c in columns if not is_skipped(c)]
    return typed + [F.col(c) for c in LINEAGE]
