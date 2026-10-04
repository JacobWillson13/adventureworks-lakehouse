select
    special_offer_id,
    description as special_offer_description,
    discount_pct,
    type as special_offer_type,
    category as special_offer_category,
    start_date,
    end_date,
    min_qty,
    max_qty,
    modified_date
from {{ source('aw_silver', 'special_offer') }}
