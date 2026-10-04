select
    business_entity_id as store_id,
    name as store_name,
    sales_person_id,
    modified_date
from {{ source('aw_silver', 'store') }}
