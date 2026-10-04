-- sales_ytd and the other snapshot figures are kept for reference; gold computes sales from orders.
select
    territory_id,
    name as territory_name,
    country_region_code,
    `group` as territory_group,
    sales_ytd,
    sales_last_year,
    cost_ytd,
    cost_last_year,
    modified_date
from {{ source('aw_silver', 'sales_territory') }}
