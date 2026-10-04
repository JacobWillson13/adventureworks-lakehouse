-- One row per vendor. credit_rating: 1 superior ... 5 below average.
select
    business_entity_id as vendor_id,
    account_number,
    name as vendor_name,
    credit_rating,
    preferred_vendor_status,
    active_flag,
    modified_date
from {{ source('aw_silver', 'vendor') }}
