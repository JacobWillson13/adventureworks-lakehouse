-- Supplier quality, one row per vendor and month over every purchase order (2011-04 to 2014-09): ordered,
-- received and rejected quantities. Not limited to the analysis window: that window exists because the sales
-- extract is truncated after May 2014, and the purchasing data is not. Roll up over months for vendor totals; rates are recomputed from the sums, never averaged.
-- Lines of purchase orders whose status is 'rejected' are counted separately: there the whole delivery
-- was refused, which is a different event from a partial rejection at receipt.
select
    l.vendor_id,
    v.vendor_name,
    v.credit_rating,
    v.preferred_vendor_status,
    v.active_flag,
    d.month_start_date,
    count(distinct l.purchase_order_id)                    as purchase_orders,
    count(*)                                               as order_lines,
    sum(l.order_qty)                                       as ordered_qty,
    sum(l.received_qty)                                    as received_qty,
    sum(l.rejected_qty)                                    as rejected_qty,
    sum(l.stocked_qty)                                     as stocked_qty,
    sum(case when l.order_status = 'rejected' then l.rejected_qty else 0 end) as rejected_qty_on_rejected_orders,
    sum(case when l.rejected_qty > 0 then 1 else 0 end)    as lines_with_rejections,
    sum(l.line_total)                                      as purchase_value,
    avg(l.planned_lead_time_days)                          as avg_planned_lead_time_days,
    avg(l.declared_lead_time_days)                         as avg_declared_lead_time_days
from {{ ref('fct_purchase_lines') }} as l
inner join {{ ref('dim_date') }} as d
    on d.date_key = l.order_date_key
inner join {{ ref('stg_vendor') }} as v
    on v.vendor_id = l.vendor_id
group by l.vendor_id, v.vendor_name, v.credit_rating, v.preferred_vendor_status, v.active_flag, d.month_start_date
