select
    sales_reason_id,
    name as sales_reason_name,
    reason_type,
    modified_date
from {{ source('aw_silver', 'sales_reason') }}
