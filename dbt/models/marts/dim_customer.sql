-- One row per customer.
--
-- customer_type:
--   store      : store_id is set. Reseller customers; person_id, when set, is the store contact (person_type SC).
--   individual : no store and person_type = 'IN'. Online retail customers.
-- Anything else stays NULL, and the not_null / accepted_values tests on customer_type fail loudly.
select
    c.customer_id,
    c.account_number,
    case
        when c.store_id is not null then 'store'
        when p.person_type = 'IN' then 'individual'
    end                                                   as customer_type,
    coalesce(s.store_name, concat_ws(' ', p.first_name, p.last_name)) as customer_name,
    c.store_id,
    s.store_name,
    c.person_id,
    p.person_type,
    p.first_name,
    p.last_name,
    c.territory_id
from {{ ref('stg_customer') }} as c
left join {{ ref('stg_store') }} as s
    on s.store_id = c.store_id
left join {{ ref('stg_person') }} as p
    on p.person_id = c.person_id
