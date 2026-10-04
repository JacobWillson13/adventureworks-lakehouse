-- Revenue reconciliation: the line revenue of each order must add up to the header's sub_total
-- (to within 0.01). Returns the orders that do not reconcile, including orders that have lines but no
-- header or a header but no lines; the test passes when it returns no rows.
with lines as (
    select sales_order_id, sum(revenue) as line_revenue
    from {{ ref('fct_sales_lines') }}
    group by sales_order_id
),

headers as (
    select sales_order_id, sub_total
    from {{ ref('stg_sales_order_header') }}
)

select
    coalesce(h.sales_order_id, l.sales_order_id) as sales_order_id,
    h.sub_total,
    l.line_revenue,
    l.line_revenue - h.sub_total                 as difference
from headers as h
full outer join lines as l
    on l.sales_order_id = h.sales_order_id
where h.sub_total is null
   or l.line_revenue is null
   or abs(l.line_revenue - h.sub_total) > 0.01
