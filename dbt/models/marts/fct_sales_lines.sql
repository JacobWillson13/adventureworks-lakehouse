-- One row per order line. Revenue = line_total (per line, lines sum to the order's sub_total).
-- Order-level attributes come from the header. Every order is kept, including June 2014: filter on
-- dim_date.is_in_analysis_window for analysis.
select
    d.sales_order_detail_id,
    d.sales_order_id,
    h.sales_order_number,
    cast(date_format(h.order_date, 'yyyyMMdd') as int)    as order_date_key,
    cast(h.order_date as date)                            as order_date,
    h.customer_id,
    h.territory_id,
    h.sales_person_id,
    h.online_order_flag,
    d.product_id,
    d.special_offer_id,
    d.order_qty,
    d.unit_price,
    d.unit_price_discount,
    d.line_total,
    d.line_total                                          as revenue
from {{ ref('stg_sales_order_detail') }} as d
inner join {{ ref('stg_sales_order_header') }} as h
    on h.sales_order_id = d.sales_order_id
