-- fct_sales_line_margin keeps exactly the lines of fct_sales_lines with the same revenue, and its cost
-- and margin add up. Returns lines missing on either side or that do not reconcile.
select
    coalesce(l.sales_order_detail_id, m.sales_order_detail_id) as sales_order_detail_id,
    l.revenue as line_revenue,
    m.revenue as margin_revenue,
    m.cost,
    m.gross_margin
from {{ ref('fct_sales_lines') }} as l
full outer join {{ ref('fct_sales_line_margin') }} as m
    on m.sales_order_detail_id = l.sales_order_detail_id
where l.sales_order_detail_id is null
   or m.sales_order_detail_id is null
   or abs(l.revenue - m.revenue) > 0.0001
   or abs(m.revenue - m.cost - m.gross_margin) > 0.0001
