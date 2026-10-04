select
    business_entity_id as sales_person_id,
    territory_id,
    sales_quota,
    bonus,
    commission_pct,
    sales_ytd,
    sales_last_year,
    modified_date
from {{ source('aw_silver', 'sales_person') }}
