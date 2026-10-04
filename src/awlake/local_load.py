"""Spark-free loader: raw AdventureWorks CSVs -> typed pandas DataFrames -> DuckDB.

Uses the same schema (config/aw_schema.json) and per-file fixes
(config/ingest_overrides.json) as the bronze layer, so local analysis and the
Databricks pipeline read the raw export identically.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pandas as pd

from .config import Config, to_snake
from .repair import rejoin_rows

csv.field_size_limit(sys.maxsize)

_PANDAS_TYPE = {"INT": "Int64", "SMALLINT": "Int64", "TINYINT": "Int64", "BIGINT": "Int64",
                "BOOLEAN": "boolean", "DOUBLE": "float64", "FLOAT": "float64"}


def _rows(path: Path, spec) -> list[list[str | None]]:
    if path.stat().st_size == 0:
        return []
    o = spec.read_options
    text = path.read_bytes().decode(o["encoding"].replace("UTF-8", "utf-8"))
    if spec.reader == "rejoin_rows":
        return rejoin_rows(text, len(spec.columns), sep=o["sep"])
    rows = []
    for i, r in enumerate(csv.reader(io.StringIO(text, newline=""), delimiter=o["sep"], quotechar=o["quote"])):
        if len(r) != len(spec.columns):
            raise ValueError(f"{path.name} row {i}: {len(r)} fields, expected {len(spec.columns)}")
        rows.append([v if v != "" else None for v in r])
    return rows


def load_table(raw_dir: Path, file_stem: str, cfg: Config) -> pd.DataFrame:
    """One raw file -> typed DataFrame with snake_case columns."""
    spec = cfg.spec(file_stem)
    df = pd.DataFrame(_rows(raw_dir / f"{file_stem}.csv", spec), columns=spec.columns, dtype="string")
    for col in cfg.schema[spec.schema_table]["columns"]:
        name, t = col["name"], col["spark_type"]
        if t in _PANDAS_TYPE:
            s = df[name]
            if t == "BOOLEAN":
                s = s.map({"1": True, "0": False, "True": True, "False": False}, na_action="ignore")
            df[name] = pd.to_numeric(s, errors="raise").astype(_PANDAS_TYPE[t]) if t != "BOOLEAN" \
                else s.astype("boolean")
        elif t.startswith("DECIMAL"):
            df[name] = pd.to_numeric(df[name], errors="raise").astype("float64")
        elif t in ("TIMESTAMP", "DATE"):
            df[name] = pd.to_datetime(df[name].str.slice(0, 26), format="ISO8601", errors="raise")
        elif name == "rowguid":
            df[name] = df[name].str.strip("{}").str.upper()
    df.columns = [to_snake(c) for c in df.columns]
    return df


def load_into_duckdb(con, raw_dir: Path, file_stems: list[str], cfg: Config | None = None) -> dict[str, int]:
    """Load tables into a DuckDB connection as snake_case table names. Returns row counts."""
    cfg = cfg or Config()
    counts = {}
    for stem in file_stems:
        df = load_table(Path(raw_dir), stem, cfg)
        name = cfg.spec(stem).bronze_table
        con.register("_tmp", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _tmp")
        con.unregister("_tmp")
        counts[name] = len(df)
        expected = cfg.expected_rows.get(stem)
        if expected is not None and expected != len(df):
            raise ValueError(f"{stem}: loaded {len(df)} rows, expected {expected}")
    return counts
