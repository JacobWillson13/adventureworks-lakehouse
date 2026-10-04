"""Silver typing (awlake.silver) on local Spark with ANSI mode on, the Databricks default.

The table tests run on the real export: each raw file goes through the bronze reader, then through
typed_columns(), and no non-null source value may come out NULL. Skipped when pyspark or data/raw is missing.
"""
import pytest

pyspark = pytest.importorskip("pyspark")

from pyspark.sql import functions as F  # noqa: E402

from conftest import ROOT  # noqa: E402
from awlake.bronze import add_lineage, read_source  # noqa: E402
from awlake.config import Config, safe_column, to_snake  # noqa: E402
from awlake.silver import LINEAGE, PERSON_NAME_COLUMNS, cast_column, is_skipped, typed_columns  # noqa: E402

cfg = Config(ROOT)
RAW = ROOT / "data" / "raw"

# Schema table -> columns promoted to silver (None = all). Mirrors src/02_silver/sales.py and purchasing.py.
SILVER_TABLES = {
    "SalesOrderHeader": None,
    "SalesOrderDetail": None,
    "Customer": None,
    "Store": None,
    "Person": PERSON_NAME_COLUMNS,
    "SalesTerritory": None,
    "SalesPerson": None,
    "Product": None,
    "ProductSubcategory": None,
    "ProductCategory": None,
    "SpecialOffer": None,
    "SpecialOfferProduct": None,
    "ProductListPriceHistory": None,
    "ProductCostHistory": None,
    "SalesReason": None,
    "SalesOrderHeaderSalesReason": None,
    "PurchaseOrderHeader": None,
    "PurchaseOrderDetail": None,
    "Vendor": None,
    "ProductVendor": None,
}


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession
    s = (SparkSession.builder.master("local[2]").appName("aw-silver-tests")
         .config("spark.ui.enabled", "false")
         .config("spark.sql.ansi.enabled", "true")
         .config("spark.sql.session.timeZone", "UTC")
         .getOrCreate())
    s.conf.set("spark.sql.ansi.enabled", "true")  # in case another module's session is reused
    yield s
    s.stop()


def one(spark, value, sql_type, spark_type, name="X"):
    col = {"name": name, "sql_type": sql_type, "spark_type": spark_type}
    df = spark.createDataFrame([(value,)], f"`{name}` string")
    return df.select(cast_column(col).alias("v")).collect()[0]["v"]


# --- single-column rules ------------------------------------------------------------------------------

def test_timestamp_with_nanoseconds_keeps_microseconds(spark):
    v = one(spark, "2014-09-12 11:15:07.263000000", "datetime", "TIMESTAMP")
    assert v.isoformat() == "2014-09-12T11:15:07.263000"


def test_timestamp_without_fraction(spark):
    assert one(spark, "2011-05-31 00:00:00", "datetime", "TIMESTAMP").isoformat() == "2011-05-31T00:00:00"


def test_unparseable_values_become_null_under_ansi(spark):
    assert one(spark, "not a date", "datetime", "TIMESTAMP") is None
    assert one(spark, "12x", "int", "INT") is None
    assert one(spark, "99999999999", "int", "INT") is None  # overflow
    assert one(spark, "abc", "money", "DECIMAL(19,4)") is None


def test_boolean_from_bit(spark):
    assert one(spark, "1", "bit", "BOOLEAN") is True
    assert one(spark, "0", "bit", "BOOLEAN") is False
    assert one(spark, "true", "bit", "BOOLEAN") is None  # not a bit export: NULL, never a silent False


def test_guid_strips_braces_and_upper_cases(spark):
    v = one(spark, "{3f5ae95e-b87d-4aed-95b4-c3797afcb74f}", "uniqueidentifier", "STRING", "rowguid")
    assert v == "3F5AE95E-B87D-4AED-95B4-C3797AFCB74F"


def test_decimal_keeps_scale(spark):
    assert str(one(spark, "3578.2700", "money", "DECIMAL(19,4)")) == "3578.2700"


def test_skipped_types():
    assert is_skipped({"sql_type": "xml"}) and is_skipped({"sql_type": "varbinary(max)"})
    assert is_skipped({"sql_type": "hierarchyid"}) and is_skipped({"sql_type": "geography"})
    assert not is_skipped({"sql_type": "nvarchar(50)"})


def test_include_rejects_unknown_columns():
    with pytest.raises(KeyError):
        typed_columns("Person", ["BusinessEntityID", "NoSuchColumn"])


# --- every silver table on the real export ------------------------------------------------------------

def bronze_df(spark, schema_table):
    path = RAW / f"{schema_table}.csv"
    if not path.exists():
        pytest.skip(f"{path} not found (clone the data repo into data/, see CLAUDE.md)")
    return add_lineage(read_source(spark, str(path), cfg.spec(schema_table)), path.name, "test-run")


@pytest.mark.parametrize("schema_table", SILVER_TABLES)
def test_casting_loses_no_values(spark, schema_table):
    include = SILVER_TABLES[schema_table]
    b = bronze_df(spark, schema_table)
    silver = b.select(*typed_columns(schema_table, include), *[F.col(c).alias(f"__src_{c}") for c in b.columns])

    columns = [c for c in cfg.schema[schema_table]["columns"]
               if not is_skipped(c) and (include is None or c["name"] in include)]
    lost = silver.select(*[
        F.sum((F.col(f"__src_{safe_column(c['name'])}").isNotNull()
               & F.col(to_snake(c["name"])).isNull()).cast("int")).alias(to_snake(c["name"]))
        for c in columns
    ]).collect()[0].asDict()

    assert {k: v for k, v in lost.items() if v} == {}
    assert b.count() == cfg.expected_rows[schema_table]


@pytest.mark.parametrize("schema_table", SILVER_TABLES)
def test_output_columns(spark, schema_table):
    b = bronze_df(spark, schema_table)
    cols = b.select(*typed_columns(schema_table, SILVER_TABLES[schema_table])).columns
    assert cols[-3:] == LINEAGE
    assert all(c == c.lower() and " " not in c for c in cols)
    assert len(cols) == len(set(cols))
