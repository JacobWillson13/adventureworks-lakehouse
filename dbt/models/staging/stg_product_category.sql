select
    product_category_id,
    name as category_name,
    modified_date
from {{ source('aw_silver', 'product_category') }}
