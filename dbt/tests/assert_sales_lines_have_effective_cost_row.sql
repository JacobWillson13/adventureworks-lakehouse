-- Effective-date join, warning level: order lines whose order date falls in none of the product's cost
-- periods. Known and documented: 64 reseller lines of discontinued products sold after their last cost
-- period ended (2013-05-29). fct_sales_line_margin carries the latest earlier cost forward for them.
-- error_if fails the build only if the set grows, or if a line has no cost period at all to carry forward.
{{ config(severity='error', warn_if='>0', error_if='>64') }}

select
    l.sales_order_detail_id,
    l.product_id,
    l.order_date,
    m.cost_source
from {{ ref('fct_sales_lines') }} as l
left join {{ ref('fct_sales_line_margin') }} as m
    on m.sales_order_detail_id = l.sales_order_detail_id
where m.cost_source is distinct from 'effective'
