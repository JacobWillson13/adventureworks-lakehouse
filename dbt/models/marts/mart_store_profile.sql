-- One row per reseller store with at least one order in the analysis window. Stores are profiled, not
-- clustered: value tiers and active/lapsed status are assigned in the analysis (awlake.analysis.segmentation).
{% set reference_date = "date_add(to_date('" ~ var('analysis_end_date') ~ "'), 1)" %}

with orders as (
    select o.customer_id, o.order_date, o.revenue, o.units, d.month_start_date
    from {{ ref('fct_orders') }} as o
    inner join {{ ref('dim_date') }} as d
        on d.date_key = o.order_date_key
    where d.is_in_analysis_window
      and o.channel = 'reseller'
)

select
    o.customer_id,
    c.store_id,
    c.store_name,
    c.territory_id,
    t.territory_name,
    t.territory_group,
    count(*)                                               as n_orders,
    count(distinct o.month_start_date)                     as active_months,
    sum(o.revenue)                                         as total_revenue,
    sum(o.revenue) / count(*)                              as aov,
    sum(o.units)                                           as units,
    min(o.order_date)                                      as first_order_date,
    max(o.order_date)                                      as last_order_date,
    datediff({{ reference_date }}, max(o.order_date))      as recency_days
from orders as o
inner join {{ ref('dim_customer') }} as c
    on c.customer_id = o.customer_id
left join {{ ref('dim_territory') }} as t
    on t.territory_id = c.territory_id
group by o.customer_id, c.store_id, c.store_name, c.territory_id, t.territory_name, t.territory_group
