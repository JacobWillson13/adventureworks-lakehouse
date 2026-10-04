-- Bridge: one row per (order, reason).
select
    sales_order_id,
    sales_reason_id,
    modified_date
from {{ source('aw_silver', 'sales_order_header_sales_reason') }}
