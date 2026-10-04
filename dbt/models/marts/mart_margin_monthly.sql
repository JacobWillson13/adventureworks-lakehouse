-- Gross margin by month, product category and channel over the analysis window.
-- gross_margin = revenue - order_qty * standard cost on the order date (fct_sales_line_margin).
select
    d.month_start_date,
    coalesce(p.category_name, 'Unassigned')                as category_name,
    m.channel,
    sum(m.order_qty)                                       as units,
    sum(m.revenue)                                         as revenue,
    sum(m.cost)                                            as cost,
    sum(m.gross_margin)                                    as gross_margin,
    sum(m.gross_margin) / nullif(sum(m.revenue), 0)        as margin_pct,
    sum(case when m.cost_source = 'carried_forward' then 1 else 0 end) as lines_cost_carried_forward
from {{ ref('fct_sales_line_margin') }} as m
inner join {{ ref('dim_date') }} as d
    on d.date_key = m.order_date_key
inner join {{ ref('dim_product') }} as p
    on p.product_id = m.product_id
where d.is_in_analysis_window
group by d.month_start_date, coalesce(p.category_name, 'Unassigned'), m.channel
