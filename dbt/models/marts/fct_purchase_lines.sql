-- One row per purchase order line: what was ordered from a vendor, and how much was received, rejected
-- and stocked. Holds every purchase order (2011-04-16 to 2014-09-22). Supplier quality uses all of them: the
-- analysis window applies to sales only.
--
-- Lead time: the source has no receipt date. due_date - order_date is the planned lead time (14 days on
-- 99% of lines) and product_vendor.average_lead_time_days is the vendor's declared figure; neither is an
-- observed delivery time.
select
    d.purchase_order_detail_id,
    d.purchase_order_id,
    cast(date_format(h.order_date, 'yyyyMMdd') as int)    as order_date_key,
    cast(h.order_date as date)                            as order_date,
    cast(h.ship_date as date)                             as ship_date,
    cast(d.due_date as date)                              as due_date,
    h.vendor_id,
    h.status_name                                         as order_status,
    d.product_id,
    d.order_qty,
    d.received_qty,
    d.rejected_qty,
    d.stocked_qty,
    d.unit_price,
    d.line_total,
    datediff(cast(d.due_date as date), cast(h.order_date as date)) as planned_lead_time_days,
    pv.average_lead_time_days                             as declared_lead_time_days
from {{ ref('stg_purchase_order_detail') }} as d
inner join {{ ref('stg_purchase_order_header') }} as h
    on h.purchase_order_id = d.purchase_order_id
left join {{ ref('stg_product_vendor') }} as pv
    on pv.product_id = d.product_id
   and pv.vendor_id = h.vendor_id
