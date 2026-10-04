-- Bridge: one row per (offer, product).
select
    special_offer_id,
    product_id,
    modified_date
from {{ source('aw_silver', 'special_offer_product') }}
