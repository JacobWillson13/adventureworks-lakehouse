-- One row per purchase order line. stocked_qty = received_qty - rejected_qty.
select
    purchase_order_detail_id,
    purchase_order_id,
    product_id,
    due_date,
    order_qty,
    unit_price,
    line_total,
    received_qty,
    rejected_qty,
    stocked_qty,
    modified_date
from {{ source('aw_silver', 'purchase_order_detail') }}
