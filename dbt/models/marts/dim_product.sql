-- One row per product, with its subcategory and category. Products that are only components (no
-- subcategory) keep NULL subcategory and category.
select
    p.product_id,
    p.product_name,
    p.product_number,
    p.product_subcategory_id,
    s.subcategory_name,
    s.product_category_id,
    c.category_name,
    p.color,
    p.size,
    p.product_line,
    p.class,
    p.style,
    p.product_model_id,
    p.make_flag,
    p.finished_goods_flag,
    p.standard_cost,
    p.list_price,
    p.sell_start_date,
    p.sell_end_date,
    p.discontinued_date
from {{ ref('stg_product') }} as p
left join {{ ref('stg_product_subcategory') }} as s
    on s.product_subcategory_id = p.product_subcategory_id
left join {{ ref('stg_product_category') }} as c
    on c.product_category_id = s.product_category_id
