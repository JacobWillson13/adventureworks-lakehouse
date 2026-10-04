-- One row per product and vendor that supplies it, with the vendor's declared average lead time in days.
select
    product_id,
    business_entity_id as vendor_id,
    average_lead_time as average_lead_time_days,
    standard_price,
    last_receipt_cost,
    last_receipt_date,
    min_order_qty,
    max_order_qty,
    on_order_qty,
    unit_measure_code,
    modified_date
from {{ source('aw_silver', 'product_vendor') }}
