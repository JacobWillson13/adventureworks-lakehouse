-- Effective-date join, error level: no order line may fall into more than one cost period of its product
-- (overlapping periods would fan out fct_sales_line_margin and double-count cost). Returns those lines.
select
    l.sales_order_detail_id,
    l.product_id,
    l.order_date,
    count(*) as matching_cost_rows
from {{ ref('fct_sales_lines') }} as l
inner join {{ ref('stg_product_cost_history') }} as c
    on c.product_id = l.product_id
   and l.order_date >= cast(c.start_date as date)
   and (c.end_date is null or l.order_date <= cast(c.end_date as date))
group by l.sales_order_detail_id, l.product_id, l.order_date
having count(*) > 1
