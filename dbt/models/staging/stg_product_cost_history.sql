-- One row per product and cost period; end_date NULL means the cost is current.
select
    product_id,
    start_date,
    end_date,
    standard_cost,
    modified_date
from {{ source('aw_silver', 'product_cost_history') }}
