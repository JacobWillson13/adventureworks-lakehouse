-- One row per product and month, from the product's first sale month to the end of the analysis window
-- (May 2014). Forecasting target: units; revenue alongside.
--
-- Months after the first sale with no sales are filled with 0 (genuine zero demand: the product was on
-- sale). Months before the first sale are not filled: the product did not exist yet, and filling them
-- would invent demand history. Units and revenue are also split by channel, because reseller batching
-- (empty reseller months) is the main source of month-to-month noise.
with lines as (
    select
        d.month_start_date,
        l.product_id,
        l.order_qty,
        l.revenue,
        l.online_order_flag
    from {{ ref('fct_sales_lines') }} as l
    inner join {{ ref('dim_date') }} as d
        on d.date_key = l.order_date_key
    where d.is_in_analysis_window
),

sales as (
    select
        product_id,
        month_start_date,
        sum(order_qty)                                            as units,
        sum(revenue)                                              as revenue,
        sum(case when online_order_flag then order_qty else 0 end)     as online_units,
        sum(case when not online_order_flag then order_qty else 0 end) as reseller_units,
        sum(case when online_order_flag then revenue else 0 end)       as online_revenue,
        sum(case when not online_order_flag then revenue else 0 end)   as reseller_revenue,
        count(*)                                                  as order_lines
    from lines
    group by product_id, month_start_date
),

first_sale as (
    select product_id, min(month_start_date) as first_month
    from sales
    group by product_id
),

months as (
    select distinct month_start_date
    from {{ ref('dim_date') }}
    where is_in_analysis_window
)

select
    f.product_id,
    p.product_name,
    p.subcategory_name,
    coalesce(p.category_name, 'Unassigned')                as category_name,
    m.month_start_date,
    f.first_month,
    coalesce(s.units, 0)                                   as units,
    coalesce(s.revenue, 0)                                 as revenue,
    coalesce(s.online_units, 0)                            as online_units,
    coalesce(s.reseller_units, 0)                          as reseller_units,
    coalesce(s.online_revenue, 0)                          as online_revenue,
    coalesce(s.reseller_revenue, 0)                        as reseller_revenue,
    coalesce(s.order_lines, 0)                             as order_lines,
    s.product_id is null                                   as is_zero_month
from first_sale as f
inner join months as m
    on m.month_start_date >= f.first_month
inner join {{ ref('dim_product') }} as p
    on p.product_id = f.product_id
left join sales as s
    on s.product_id = f.product_id
   and s.month_start_date = m.month_start_date
