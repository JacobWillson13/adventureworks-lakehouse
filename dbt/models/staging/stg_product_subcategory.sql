select
    product_subcategory_id,
    product_category_id,
    name as subcategory_name,
    modified_date
from {{ source('aw_silver', 'product_subcategory') }}
