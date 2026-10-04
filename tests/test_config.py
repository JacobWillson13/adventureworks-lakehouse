
import pytest
from conftest import ROOT

from awlake.config import Config, safe_column, to_snake

cfg = Config(ROOT)


def test_schema_covers_all_ddl_tables():
    assert len(cfg.schema) == 71
    assert sum(len(t["columns"]) for t in cfg.schema.values()) == 486


def test_column_with_space_is_parsed():
    cols = [c["name"] for c in cfg.schema["AWBuildVersion"]["columns"]]
    assert cols == ["SystemInformationID", "Database Version", "VersionDate", "ModifiedDate"]
    assert cfg.spec("AWBuildVersion").bronze_columns[1] == "Database_Version"


def test_computed_columns_kept_in_order():
    cols = [c["name"] for c in cfg.schema["Customer"]["columns"]]
    assert cols.index("AccountNumber") == 4  # export includes computed columns in table order


@pytest.mark.parametrize("name,expected", [
    ("SalesOrderHeader", "sales_order_header"),
    ("AWBuildVersion", "aw_build_version"),
    ("ProductModelProductDescriptionCulture", "product_model_product_description_culture"),
    ("JobCandidate_TOREMOVE", "job_candidate_toremove"),
])
def test_to_snake(name, expected):
    assert to_snake(name) == expected


def test_safe_column():
    assert safe_column("Database Version") == "Database_Version"


def test_overrides_reference_real_tables():
    for stem, ov in cfg.overrides.items():
        if stem.startswith("_") or ov.get("exclude"):
            continue
        assert ov.get("schema_from", stem) in cfg.schema, stem


def test_every_expected_file_resolves():
    for stem in cfg.expected_rows:
        spec = cfg.spec(stem)
        assert spec.columns and not spec.exclude


def test_special_cases():
    assert cfg.spec("Address").read_options["encoding"] == "windows-1252"
    assert cfg.spec("ProductReview").reader == "rejoin_rows"
    assert cfg.spec("JobCandidate_TOREMOVE").exclude
    pmo = cfg.spec("ProductModelorg")
    assert pmo.bronze_table == "product_model_org" and pmo.schema_table == "ProductModel"


def test_bronze_table_names_unique():
    names = [cfg.spec(s).bronze_table for s in cfg.expected_rows]
    assert len(names) == len(set(names))
