# Silver layer, sales domain: Lakeflow Declarative Pipeline source.
#
# Each function below defines one materialized view in the pipeline's target schema (aw_silver).
# Bronze is fully overwritten on every run, so it is not an append-only source; materialized views
# (recomputed from source on each update) are the right dataset type, not streaming tables.
#
# Typing lives in awlake.silver.typed_columns (importable because the pipeline's root_path is src/):
# it builds the select list from config/aw_schema.json with try_* casts, so a value that cannot be
# parsed becomes NULL instead of crashing the update, and the expectations below decide what happens
# to that row.
#
# Severity reflects business impact:
#   fail -> the table is unusable without it; stop the update and investigate
#   drop -> the row cannot be used for analysis; remove it, but record how many were removed
#   warn -> the row is usable but suspicious; keep it and record the violation
# Every table fails on a missing primary key and drops rows whose required timestamps did not parse.
# Money and quantity checks drop on transactional rows (an order line with a negative price would
# corrupt revenue) and warn on reference rows (dropping a product or territory would orphan the
# orders that point at it). Cross-table checks belong to the dbt tests in gold, not here.
from pyspark import pipelines as dp

from awlake.silver import PERSON_NAME_COLUMNS, typed_columns

# Set in the pipeline configuration (resources/aw_silver.pipeline.yml), so this file has no
# hard-coded catalog and works unchanged in any workspace.
BRONZE = spark.conf.get("bronze_schema")  # noqa: F821  (spark is provided by the pipeline runtime)


def bronze(table: str, schema_table: str, include: list[str] | None = None):
    return spark.read.table(f"{BRONZE}.{table}").select(*typed_columns(schema_table, include))  # noqa: F821


# ---------------------------------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------------------------------

@dp.materialized_view(
    name="sales_order_header",
    comment="One row per sales order, typed from bronze. Revenue = sub_total (excludes tax and freight).",
)
@dp.expect_or_fail("order_id_present", "sales_order_id IS NOT NULL")
@dp.expect_or_drop("order_date_parsed", "order_date IS NOT NULL")
@dp.expect_or_drop("subtotal_non_negative", "sub_total >= 0")
@dp.expect("total_due_reconciles", "ABS(total_due - (sub_total + tax_amt + freight)) < 0.01")
@dp.expect("due_on_or_after_order", "due_date >= order_date")
@dp.expect("status_in_range", "status BETWEEN 1 AND 6")
def sales_order_header():
    return bronze("sales_order_header", "SalesOrderHeader")


@dp.materialized_view(
    name="sales_order_detail",
    comment="One row per order line. line_total sums to the header's sub_total.",
)
@dp.expect_or_fail("pk_present", "sales_order_id IS NOT NULL AND sales_order_detail_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
# Lines are the revenue and units facts, so bad amounts are dropped rather than summed. Quantity must be
# positive (the source's own CHECK constraint): a zero-unit line is not a sale.
@dp.expect_or_drop("order_qty_positive", "order_qty > 0")
@dp.expect_or_drop("unit_price_non_negative", "unit_price >= 0")
@dp.expect_or_drop("line_total_non_negative", "line_total >= 0")
# The discount is already baked into line_total, which is checked above; an odd rate alone is a warning.
@dp.expect("discount_in_range", "unit_price_discount BETWEEN 0 AND 1")
def sales_order_detail():
    return bronze("sales_order_detail", "SalesOrderDetail")


@dp.materialized_view(
    name="sales_order_header_sales_reason",
    comment="Bridge: the reasons a customer gave for an order (online orders only).",
)
@dp.expect_or_fail("pk_present", "sales_order_id IS NOT NULL AND sales_reason_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
def sales_order_header_sales_reason():
    return bronze("sales_order_header_sales_reason", "SalesOrderHeaderSalesReason")


@dp.materialized_view(name="sales_reason", comment="Lookup of purchase reasons (price, promotion, review, ...).")
@dp.expect_or_fail("pk_present", "sales_reason_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
def sales_reason():
    return bronze("sales_reason", "SalesReason")


# ---------------------------------------------------------------------------------------------------
# Customers, stores, people, sales staff, territories
# ---------------------------------------------------------------------------------------------------

@dp.materialized_view(
    name="customer",
    comment="One row per customer: person_id set for individuals, store_id set for resellers.",
)
@dp.expect_or_fail("pk_present", "customer_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
def customer():
    return bronze("customer", "Customer")


@dp.materialized_view(name="store", comment="Reseller stores. Survey XML (demographics) stays in bronze for now.")
@dp.expect_or_fail("pk_present", "business_entity_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
def store():
    return bronze("store", "Store")


@dp.materialized_view(
    name="person",
    comment="People: key and name columns only. Contact details and survey XML stay in bronze.",
)
@dp.expect_or_fail("pk_present", "business_entity_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
def person():
    return bronze("person", "Person", PERSON_NAME_COLUMNS)


@dp.materialized_view(name="sales_person", comment="Sales staff with quota, bonus and commission.")
@dp.expect_or_fail("pk_present", "business_entity_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
# Reference rows: orders point at sales people, so odd compensation figures warn instead of dropping.
@dp.expect("sales_quota_non_negative", "sales_quota IS NULL OR sales_quota >= 0")
@dp.expect("bonus_non_negative", "bonus >= 0")
@dp.expect("commission_pct_non_negative", "commission_pct >= 0")
@dp.expect("sales_ytd_non_negative", "sales_ytd >= 0")
@dp.expect("sales_last_year_non_negative", "sales_last_year >= 0")
def sales_person():
    return bronze("sales_person", "SalesPerson")


@dp.materialized_view(
    name="sales_territory",
    comment="Sales territories. The YTD figures are source snapshots; gold recomputes sales from orders.",
)
@dp.expect_or_fail("pk_present", "territory_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
# Reference rows, and the snapshot figures are not used for revenue: warn only.
@dp.expect("sales_ytd_non_negative", "sales_ytd >= 0")
@dp.expect("sales_last_year_non_negative", "sales_last_year >= 0")
@dp.expect("cost_ytd_non_negative", "cost_ytd >= 0")
@dp.expect("cost_last_year_non_negative", "cost_last_year >= 0")
def sales_territory():
    return bronze("sales_territory", "SalesTerritory")


# ---------------------------------------------------------------------------------------------------
# Products, prices and costs
# ---------------------------------------------------------------------------------------------------

@dp.materialized_view(name="product", comment="Products with current list price and standard cost.")
@dp.expect_or_fail("pk_present", "product_id IS NOT NULL")
@dp.expect_or_drop("sell_start_date_parsed", "sell_start_date IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
# Reference rows: order lines point at products, so odd prices or stock levels warn instead of dropping.
# Prices over time come from the history tables, which drop bad rows.
@dp.expect("list_price_non_negative", "list_price >= 0")
@dp.expect("standard_cost_non_negative", "standard_cost >= 0")
@dp.expect("safety_stock_level_non_negative", "safety_stock_level >= 0")
@dp.expect("reorder_point_non_negative", "reorder_point >= 0")
def product():
    return bronze("product", "Product")


@dp.materialized_view(name="product_subcategory", comment="Product subcategories (37), each in one category.")
@dp.expect_or_fail("pk_present", "product_subcategory_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
def product_subcategory():
    return bronze("product_subcategory", "ProductSubcategory")


@dp.materialized_view(name="product_category", comment="Product categories: Bikes, Components, Clothing, Accessories.")
@dp.expect_or_fail("pk_present", "product_category_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
def product_category():
    return bronze("product_category", "ProductCategory")


@dp.materialized_view(
    name="product_list_price_history",
    comment="List price per product over time; end_date NULL means current. Joined by effective date in gold.",
)
@dp.expect_or_fail("pk_present", "product_id IS NOT NULL AND start_date IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
# The price feeds effective-date joins directly; a wrong price is worse than a missing one, which gold's
# join-coverage tests will surface.
@dp.expect_or_drop("list_price_non_negative", "list_price >= 0")
def product_list_price_history():
    return bronze("product_list_price_history", "ProductListPriceHistory")


@dp.materialized_view(
    name="product_cost_history",
    comment="Standard cost per product over time; end_date NULL means current. Feeds margin over time.",
)
@dp.expect_or_fail("pk_present", "product_id IS NOT NULL AND start_date IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
# Same reasoning as list price: a negative cost would silently inflate margin, so the row is dropped.
@dp.expect_or_drop("standard_cost_non_negative", "standard_cost >= 0")
def product_cost_history():
    return bronze("product_cost_history", "ProductCostHistory")


# ---------------------------------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------------------------------

@dp.materialized_view(name="special_offer", comment="Promotions and volume discounts. ID 1 = 'No Discount'.")
@dp.expect_or_fail("pk_present", "special_offer_id IS NOT NULL")
@dp.expect_or_drop("start_date_parsed", "start_date IS NOT NULL")
@dp.expect_or_drop("end_date_parsed", "end_date IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
# Reference rows: every order line points at an offer, so odd values warn instead of dropping.
@dp.expect("discount_pct_in_range", "discount_pct BETWEEN 0 AND 1")
@dp.expect("min_qty_non_negative", "min_qty >= 0")
@dp.expect("max_qty_non_negative", "max_qty IS NULL OR max_qty >= 0")
def special_offer():
    return bronze("special_offer", "SpecialOffer")


@dp.materialized_view(name="special_offer_product", comment="Bridge: which products each offer applies to.")
@dp.expect_or_fail("pk_present", "special_offer_id IS NOT NULL AND product_id IS NOT NULL")
@dp.expect_or_drop("modified_date_parsed", "modified_date IS NOT NULL")
def special_offer_product():
    return bronze("special_offer_product", "SpecialOfferProduct")
