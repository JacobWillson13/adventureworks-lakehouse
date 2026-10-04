-- Channels never overlap (profiling): every online order belongs to an individual customer and every
-- reseller order to a store. Returns the orders that break the rule.
select
    o.sales_order_id,
    o.channel,
    c.customer_type
from {{ ref('fct_orders') }} as o
left join {{ ref('dim_customer') }} as c
    on c.customer_id = o.customer_id
where c.customer_type is null
   or (o.channel = 'online' and c.customer_type <> 'individual')
   or (o.channel = 'reseller' and c.customer_type <> 'store')
