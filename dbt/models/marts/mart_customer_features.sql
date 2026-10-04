-- One row per individual (online) customer with at least one order in the analysis window: RFM-style
-- features for segmentation. Reseller stores are profiled separately (mart_store_profile).
--
-- Recency and tenure are days to the day after the window ends (2014-06-01), as in the prototype.
-- bike_share is the share of the customer's revenue from Bikes; n_categories counts distinct categories.
{% set reference_date = "date_add(to_date('" ~ var('analysis_end_date') ~ "'), 1)" %}

with orders as (
    select o.customer_id, o.sales_order_id, o.order_date, o.revenue, o.units
    from {{ ref('fct_orders') }} as o
    inner join {{ ref('dim_date') }} as d
        on d.date_key = o.order_date_key
    inner join {{ ref('dim_customer') }} as c
        on c.customer_id = o.customer_id
    where d.is_in_analysis_window
      and c.customer_type = 'individual'
),

mix as (
    select
        l.customer_id,
        count(distinct p.category_name)                                           as n_categories,
        sum(case when p.category_name = 'Bikes' then l.revenue else 0 end) / sum(l.revenue) as bike_share
    from {{ ref('fct_sales_lines') }} as l
    inner join orders as o
        on o.sales_order_id = l.sales_order_id
    inner join {{ ref('dim_product') }} as p
        on p.product_id = l.product_id
    group by l.customer_id
)

select
    o.customer_id,
    c.territory_id,
    min(o.order_date)                                      as first_order_date,
    max(o.order_date)                                      as last_order_date,
    count(*)                                               as n_orders,
    sum(o.revenue)                                         as total_revenue,
    sum(o.revenue) / count(*)                              as aov,
    sum(o.units)                                           as units,
    sum(o.units) / count(*)                                as units_per_order,
    datediff({{ reference_date }}, max(o.order_date))      as recency_days,
    datediff({{ reference_date }}, min(o.order_date))      as tenure_days,
    max(m.n_categories)                                    as n_categories,
    max(m.bike_share)                                      as bike_share,
    min(o.order_date) < to_date('2013-06-01')              as first_order_before_jun2013
from orders as o
inner join {{ ref('dim_customer') }} as c
    on c.customer_id = o.customer_id
left join mix as m
    on m.customer_id = o.customer_id
group by o.customer_id, c.territory_id
