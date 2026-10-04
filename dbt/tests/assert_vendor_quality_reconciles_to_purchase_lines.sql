-- mart_vendor_quality must carry exactly the received and rejected quantities of every purchase line in
-- fct_purchase_lines (all purchase orders, no analysis window). Returns a row if either total differs.
with facts as (
    select sum(received_qty) as received_qty, sum(rejected_qty) as rejected_qty
    from {{ ref('fct_purchase_lines') }}
),

mart as (
    select sum(received_qty) as received_qty, sum(rejected_qty) as rejected_qty
    from {{ ref('mart_vendor_quality') }}
)

select f.received_qty as fact_received, m.received_qty as mart_received,
       f.rejected_qty as fact_rejected, m.rejected_qty as mart_rejected
from facts as f
cross join mart as m
where f.received_qty <> m.received_qty
   or f.rejected_qty <> m.rejected_qty
