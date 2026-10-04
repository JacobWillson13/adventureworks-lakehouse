# Silver layer, sales domain: Lakeflow Declarative Pipeline source.
#
# Each function below defines one materialized view in the pipeline's target schema (aw_silver).
# Bronze is fully overwritten on every run, so it is not an append-only source; materialized views
# (recomputed from source on each update) are the right dataset type, not streaming tables.
#
# Casting uses try_* functions: a value that cannot be parsed becomes NULL instead of crashing the
# update, and the expectations below then decide what happens to that row.
from pyspark import pipelines as dp
from pyspark.sql import functions as F

# Set in the pipeline configuration (resources/aw_silver.pipeline.yml), so this file has no
# hard-coded catalog and works unchanged in any workspace.
BRONZE = spark.conf.get("bronze_schema")  # noqa: F821  (spark is provided by the pipeline runtime)


def ts(col: str):
    """Bronze timestamps look like '2011-05-31 00:00:00' or '2014-09-12 11:15:07.263000000'.
    Spark keeps microseconds, so trim to 26 characters before parsing."""
    return F.try_to_timestamp(F.substring(F.col(col), 1, 26))


def guid(col: str):
    """Some tables wrap GUIDs in {braces}; normalize to bare upper-case."""
    return F.upper(F.regexp_replace(F.col(col), r"[{}]", ""))


@dp.materialized_view(
    name="sales_order_header",
    comment="One row per sales order, typed from bronze. Revenue = sub_total (excludes tax and freight).",
)
# Severity reflects business impact:
#   fail -> the table is unusable without it; stop the update and investigate
#   drop -> the row cannot be used for analysis; remove it, but record how many were removed
#   warn -> the row is usable but suspicious; keep it and record the violation
@dp.expect_or_fail("order_id_present", "sales_order_id IS NOT NULL")
@dp.expect_or_drop("order_date_parsed", "order_date IS NOT NULL")
@dp.expect_or_drop("subtotal_non_negative", "sub_total >= 0")
@dp.expect("total_due_reconciles", "ABS(total_due - (sub_total + tax_amt + freight)) < 0.01")
@dp.expect("due_on_or_after_order", "due_date >= order_date")
@dp.expect("status_in_range", "status BETWEEN 1 AND 6")
def sales_order_header():
    b = spark.read.table(f"{BRONZE}.sales_order_header")  # noqa: F821
    return b.select(
        F.col("SalesOrderID").try_cast("int").alias("sales_order_id"),
        F.col("RevisionNumber").try_cast("tinyint").alias("revision_number"),
        ts("OrderDate").alias("order_date"),
        ts("DueDate").alias("due_date"),
        ts("ShipDate").alias("ship_date"),
        F.col("Status").try_cast("tinyint").alias("status"),
        (F.col("OnlineOrderFlag") == "1").alias("online_order_flag"),
        F.col("SalesOrderNumber").alias("sales_order_number"),
        F.col("PurchaseOrderNumber").alias("purchase_order_number"),
        F.col("AccountNumber").alias("account_number"),
        F.col("CustomerID").try_cast("int").alias("customer_id"),
        F.col("SalesPersonID").try_cast("int").alias("sales_person_id"),
        F.col("TerritoryID").try_cast("int").alias("territory_id"),
        F.col("BillToAddressID").try_cast("int").alias("bill_to_address_id"),
        F.col("ShipToAddressID").try_cast("int").alias("ship_to_address_id"),
        F.col("ShipMethodID").try_cast("int").alias("ship_method_id"),
        F.col("CreditCardID").try_cast("int").alias("credit_card_id"),
        F.col("CurrencyRateID").try_cast("int").alias("currency_rate_id"),
        F.col("SubTotal").try_cast("decimal(19,4)").alias("sub_total"),
        F.col("TaxAmt").try_cast("decimal(19,4)").alias("tax_amt"),
        F.col("Freight").try_cast("decimal(19,4)").alias("freight"),
        F.col("TotalDue").try_cast("decimal(19,4)").alias("total_due"),
        F.col("Comment").alias("comment"),
        guid("rowguid").alias("rowguid"),
        ts("ModifiedDate").alias("modified_date"),
        F.col("_source_file"),
        F.col("_ingested_at"),
    )
