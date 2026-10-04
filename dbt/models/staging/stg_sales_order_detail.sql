-- One row per order line.
select
    sales_order_detail_id,
    sales_order_id,
    product_id,
    special_offer_id,
    carrier_tracking_number,
    order_qty,
    unit_price,
    unit_price_discount,
    line_total,
    modified_date
from {{ source('aw_silver', 'sales_order_detail') }}
