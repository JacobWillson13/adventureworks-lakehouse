-- One row per sales order. Revenue = sub_total (excludes tax and freight); tax_amt, freight and total_due
-- are kept so revenue can be reconciled to what was billed. Every order is kept, including June 2014:
-- filter on dim_date.is_in_analysis_window for analysis.
--
-- Lines are aggregated to one row per order BEFORE the join, so the header grain never fans out.
-- Left join: an order with no lines keeps its row (line_count = 0) instead of disappearing, and
-- tests/assert_sales_lines_reconcile_to_order_subtotal.sql flags it.
with lines as (
    select
        sales_order_id,
        count(*)       as line_count,
        sum(order_qty) as units
    from {{ ref('stg_sales_order_detail') }}
    group by sales_order_id
)

select
    h.sales_order_id,
    h.sales_order_number,
    cast(date_format(h.order_date, 'yyyyMMdd') as int)    as order_date_key,
    cast(h.order_date as date)                            as order_date,
    h.customer_id,
    h.territory_id,
    h.sales_person_id,
    -- NULL flag stays NULL so the not_null test on channel fails loudly.
    case
        when h.online_order_flag then 'online'
        when not h.online_order_flag then 'reseller'
    end                                                   as channel,
    h.sub_total                                           as revenue,
    h.tax_amt,
    h.freight,
    h.total_due,
    coalesce(l.line_count, 0)                             as line_count,
    coalesce(l.units, 0)                                  as units
from {{ ref('stg_sales_order_header') }} as h
left join lines as l
    on l.sales_order_id = h.sales_order_id
