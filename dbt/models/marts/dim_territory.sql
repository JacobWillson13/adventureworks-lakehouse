-- One row per sales territory. The source's YTD snapshot figures are left out: sales come from the facts.
select
    territory_id,
    territory_name,
    country_region_code,
    territory_group
from {{ ref('stg_sales_territory') }}
