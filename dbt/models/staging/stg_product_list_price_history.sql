-- One row per product and price period; end_date NULL means the price is current.
select
    product_id,
    start_date,
    end_date,
    list_price,
    modified_date
from {{ source('aw_silver', 'product_list_price_history') }}
