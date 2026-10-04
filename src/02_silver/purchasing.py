# Silver layer, purchasing domain: Lakeflow Declarative Pipeline source.
#
# The four tables supplier quality needs: purchase orders (header and lines), vendors, and the
# product-vendor list with each vendor's declared lead time and price. Same pattern and severity rules as
# sales.py: fail on a missing primary key, drop rows whose required dates or quantities cannot be used,
# warn on reference rows and on cross-column checks that do not make a row unusable.
from pyspark import pipelines as dp

from awlake.silver import typed_columns

BRONZE = spark.conf.get("bronze_schema")  # noqa: F821  (spark is provided by the pipeline runtime)


def bronze(table: str, schema_table: str):
    return spark.read.table(f"{BRONZE}.{table}").select(*typed_columns(schema_table))  # noqa: F821


@dp.materialized_view(
    name="purchase_order_header",
    comment="One row per purchase order to a vendor. Status: 1 pending, 2 approved, 3 rejected, 4 complete.",
)
@dp.expect_or_fail("purchase_order_id_present", "purchase_order_id IS NOT NULL")
@dp.expect_or_drop("order_date_parsed", "order_date IS NOT NULL")
# Supplier quality is reported per vendor, so an order without one cannot be attributed.
@dp.expect_or_drop("vendor_id_present", "vendor_id IS NOT NULL")
@dp.expect_or_drop("subtotal_non_negative", "sub_total >= 0")
@dp.expect("total_due_reconciles", "ABS(total_due - (sub_total + tax_amt + freight)) < 0.01")
@dp.expect("ship_on_or_after_order", "ship_date IS NULL OR ship_date >= order_date")
@dp.expect("status_in_range", "status BETWEEN 1 AND 4")
def purchase_order_header():
    return bronze("purchase_order_header", "PurchaseOrderHeader")


@dp.materialized_view(
    name="purchase_order_detail",
    comment="One row per purchase order line: ordered, received, rejected and stocked quantities.",
)
@dp.expect_or_fail("pk_present", "purchase_order_id IS NOT NULL AND purchase_order_detail_id IS NOT NULL")
@dp.expect_or_drop("due_date_parsed", "due_date IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
# The quantities are the supplier quality measures: a negative or missing one would corrupt rejection
# rates, so the row is dropped rather than summed.
@dp.expect_or_drop("order_qty_positive", "order_qty > 0")
@dp.expect_or_drop("unit_price_non_negative", "unit_price >= 0")
@dp.expect_or_drop("received_qty_non_negative", "received_qty >= 0")
@dp.expect_or_drop("rejected_qty_non_negative", "rejected_qty >= 0")
# Cross-column consistency: suspicious but still countable, so warn.
@dp.expect("rejected_within_received", "rejected_qty <= received_qty")
@dp.expect("stocked_is_received_minus_rejected", "ABS(stocked_qty - (received_qty - rejected_qty)) < 0.01")
@dp.expect("line_total_is_qty_times_price", "ABS(line_total - order_qty * unit_price) < 0.01")
def purchase_order_detail():
    return bronze("purchase_order_detail", "PurchaseOrderDetail")


@dp.materialized_view(name="vendor", comment="Vendors (suppliers) with credit rating and preferred/active flags.")
@dp.expect_or_fail("pk_present", "business_entity_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
# Reference rows: purchase orders point at vendors, so odd values warn instead of dropping.
@dp.expect("credit_rating_in_range", "credit_rating BETWEEN 1 AND 5")
def vendor():
    return bronze("vendor", "Vendor")


@dp.materialized_view(
    name="product_vendor",
    comment="Which vendors supply which products, with declared average lead time (days) and standard price.",
)
@dp.expect_or_fail("pk_present", "product_id IS NOT NULL AND business_entity_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
@dp.expect("average_lead_time_positive", "average_lead_time > 0")
@dp.expect("standard_price_non_negative", "standard_price >= 0")
@dp.expect("min_order_qty_within_max", "min_order_qty <= max_order_qty")
def product_vendor():
    return bronze("product_vendor", "ProductVendor")
