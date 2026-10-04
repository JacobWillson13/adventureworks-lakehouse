-- One row per month and channel over the analysis window (May 2011 to May 2014), including months with
-- no orders. Resellers order in monthly batches and some months have none (e.g. Feb and Apr 2014); those
-- months are kept as explicit zeros so trends and forecasts see the gap instead of skipping it.
with months as (
    select distinct month_start_date
    from {{ ref('dim_date') }}
    where is_in_analysis_window
      and month_start_date >= (select cast(date_trunc('MONTH', min(order_date)) as date) from {{ ref('fct_orders') }})
),

channels as (
    select 'online' as channel
    union all
    select 'reseller' as channel
),

orders as (
    select
        d.month_start_date,
        o.channel,
        count(*)                       as orders,
        count(distinct o.customer_id)  as customers,
        sum(o.revenue)                 as revenue,
        sum(o.units)                   as units
    from {{ ref('fct_orders') }} as o
    inner join {{ ref('dim_date') }} as d
        on d.date_key = o.order_date_key
    where d.is_in_analysis_window
    group by d.month_start_date, o.channel
)

select
    m.month_start_date,
    c.channel,
    coalesce(o.orders, 0)                                  as orders,
    coalesce(o.customers, 0)                               as customers,
    coalesce(o.revenue, 0)                                 as revenue,
    coalesce(o.units, 0)                                   as units,
    o.orders is null                                       as is_empty_month
from months as m
cross join channels as c
left join orders as o
    on o.month_start_date = m.month_start_date
   and o.channel = c.channel
