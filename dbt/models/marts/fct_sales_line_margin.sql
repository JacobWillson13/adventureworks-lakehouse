-- One row per order line with the product's standard cost on the order date: margin over time.
--
-- Effective-date join: a cost period applies when start_date <= order_date <= end_date; end_date NULL
-- means the period is still open. Periods are whole days (end_date is the day before the next start_date),
-- so both bounds are inclusive and at most one period matches; tests/assert_sales_lines_match_at_most_one_cost_row.sql
-- fails the build otherwise.
--
-- 64 reseller lines (discontinued products sold after their last cost period ended in May 2013) match no
-- period. They keep the product's latest earlier cost (cost_source = 'carried_forward'), so every line has
-- a cost; tests/assert_sales_lines_have_effective_cost_row.sql lists them as a warning.
with lines as (
    select
        sales_order_detail_id,
        sales_order_id,
        order_date_key,
        order_date,
        online_order_flag,
        product_id,
        order_qty,
        revenue
    from {{ ref('fct_sales_lines') }}
),

cost as (
    select
        product_id,
        cast(start_date as date)  as start_date,
        cast(end_date as date)    as end_date,
        standard_cost
    from {{ ref('stg_product_cost_history') }}
),

effective as (
    select
        l.sales_order_detail_id,
        c.start_date,
        c.standard_cost
    from lines as l
    inner join cost as c
        on c.product_id = l.product_id
       and l.order_date >= c.start_date
       and (c.end_date is null or l.order_date <= c.end_date)
),

carried_forward as (
    select sales_order_detail_id, start_date, standard_cost
    from (
        select
            l.sales_order_detail_id,
            c.start_date,
            c.standard_cost,
            row_number() over (partition by l.sales_order_detail_id order by c.start_date desc) as rn
        from lines as l
        inner join cost as c
            on c.product_id = l.product_id
           and c.end_date < l.order_date
    ) as ranked
    where rn = 1
)

select
    l.sales_order_detail_id,
    l.sales_order_id,
    l.order_date_key,
    l.order_date,
    case when l.online_order_flag then 'online' else 'reseller' end   as channel,
    l.product_id,
    l.order_qty,
    l.revenue,
    coalesce(e.standard_cost, cf.standard_cost)                        as unit_standard_cost,
    l.order_qty * coalesce(e.standard_cost, cf.standard_cost)          as cost,
    l.revenue - l.order_qty * coalesce(e.standard_cost, cf.standard_cost) as gross_margin,
    coalesce(e.start_date, cf.start_date)                              as cost_start_date,
    case
        when e.sales_order_detail_id is not null then 'effective'
        when cf.sales_order_detail_id is not null then 'carried_forward'
    end                                                                as cost_source
from lines as l
left join effective as e
    on e.sales_order_detail_id = l.sales_order_detail_id
left join carried_forward as cf
    on cf.sales_order_detail_id = l.sales_order_detail_id
