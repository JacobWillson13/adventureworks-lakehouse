-- The analysis marts must carry exactly the in-window revenue of the facts they aggregate (within 0.01).
-- Returns one row per mart whose total differs.
with window_orders as (
    select o.*
    from {{ ref('fct_orders') }} as o
    inner join {{ ref('dim_date') }} as d on d.date_key = o.order_date_key
    where d.is_in_analysis_window
),

window_lines as (
    select l.*
    from {{ ref('fct_sales_lines') }} as l
    inner join {{ ref('dim_date') }} as d on d.date_key = l.order_date_key
    where d.is_in_analysis_window
),

expected as (
    select 'mart_channel_monthly' as mart, (select sum(revenue) from window_orders) as fact_revenue,
           (select sum(revenue) from {{ ref('mart_channel_monthly') }}) as mart_revenue
    union all
    select 'mart_product_monthly', (select sum(revenue) from window_lines),
           (select sum(revenue) from {{ ref('mart_product_monthly') }})
    union all
    select 'mart_margin_monthly', (select sum(revenue) from window_lines),
           (select sum(revenue) from {{ ref('mart_margin_monthly') }})
    union all
    select 'mart_customer_features', (select sum(revenue) from window_orders where channel = 'online'),
           (select sum(total_revenue) from {{ ref('mart_customer_features') }})
    union all
    select 'mart_store_profile', (select sum(revenue) from window_orders where channel = 'reseller'),
           (select sum(total_revenue) from {{ ref('mart_store_profile') }})
)

select *
from expected
where mart_revenue is null
   or abs(fact_revenue - mart_revenue) > 0.01
