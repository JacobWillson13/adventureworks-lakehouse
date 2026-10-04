-- One row per purchase order to a vendor. status: 1 pending, 2 approved, 3 rejected, 4 complete.
select
    purchase_order_id,
    revision_number,
    status,
    case status
        when 1 then 'pending'
        when 2 then 'approved'
        when 3 then 'rejected'
        when 4 then 'complete'
    end as status_name,
    employee_id,
    vendor_id,
    ship_method_id,
    order_date,
    ship_date,
    sub_total,
    tax_amt,
    freight,
    total_due,
    modified_date
from {{ source('aw_silver', 'purchase_order_header') }}
