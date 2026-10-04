-- Order revenue must equal the sum of its line revenue (within 0.01). Returns the orders that do not
-- reconcile, including orders with no lines and lines whose order is missing from fct_orders.
with lines as (
    select sales_order_id, sum(revenue) as line_revenue
    from {{ ref('fct_sales_lines') }}
    group by sales_order_id
)

select
    coalesce(o.sales_order_id, l.sales_order_id) as sales_order_id,
    o.revenue                                    as order_revenue,
    l.line_revenue,
    l.line_revenue - o.revenue                   as difference
from {{ ref('fct_orders') }} as o
full outer join lines as l
    on l.sales_order_id = o.sales_order_id
where o.revenue is null
   or l.line_revenue is null
   or abs(l.line_revenue - o.revenue) > 0.01
