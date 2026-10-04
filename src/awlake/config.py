"""Load the repo's config files and derive table/column names.

Pure Python (no Spark) so it runs in local tests and in Databricks notebooks.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

EXCLUDED = "excluded"


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: cwd) until config/aw_schema.json is found."""
    here = (start or Path.cwd()).resolve()
    for p in (here, *here.parents):
        if (p / "config" / "aw_schema.json").exists():
            return p
    raise FileNotFoundError(f"config/aw_schema.json not found above {here}")


def to_snake(name: str) -> str:
    """SalesOrderHeader -> sales_order_header, AWBuildVersion -> aw_build_version."""
    s = re.sub(r"[^0-9A-Za-z]+", "_", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return re.sub(r"_+", "_", s).strip("_").lower()


def safe_column(name: str) -> str:
    """Delta-safe column name that keeps the source spelling ('Database Version' -> 'Database_Version')."""
    return re.sub(r"[^0-9A-Za-z_]", "_", name)


@dataclass(frozen=True)
class SourceSpec:
    """Everything needed to ingest one raw file into bronze."""

    file_stem: str
    schema_table: str
    bronze_table: str
    columns: list[str]
    read_options: dict
    reader: str = "csv"
    exclude: bool = False
    note: str = ""
    expected_rows: int | None = None
    bronze_columns: list[str] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bronze_columns", [safe_column(c) for c in self.columns])


class Config:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or find_repo_root()
        cfg = self.root / "config"
        self.schema: dict = json.loads((cfg / "aw_schema.json").read_text())
        self.overrides: dict = json.loads((cfg / "ingest_overrides.json").read_text())
        counts = json.loads((cfg / "expected_row_counts.json").read_text())
        self.expected_rows: dict[str, int] = {k: v for k, v in counts.items() if not k.startswith("_")}
        self.defaults: dict = self.overrides.get("_defaults", {})

    def spec(self, file_stem: str) -> SourceSpec:
        ov = self.overrides.get(file_stem, {})
        schema_table = ov.get("schema_from", file_stem)
        if not ov.get("exclude") and schema_table not in self.schema:
            raise KeyError(f"No schema for '{file_stem}' (add it to aw_schema.json or ingest_overrides.json)")
        columns = [c["name"] for c in self.schema.get(schema_table, {}).get("columns", [])]
        opts = {**self.defaults, **{k: v for k, v in ov.items() if k in self.defaults}}
        return SourceSpec(
            file_stem=file_stem,
            schema_table=schema_table,
            bronze_table=ov.get("bronze_table", to_snake(file_stem)),
            columns=columns,
            read_options=opts,
            reader=ov.get("reader", "csv"),
            exclude=bool(ov.get("exclude", False)),
            note=ov.get("note", ""),
            expected_rows=self.expected_rows.get(file_stem),
        )
