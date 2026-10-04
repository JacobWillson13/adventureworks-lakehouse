-- person_id is set for individuals and store contacts, store_id for reseller stores.
select
    customer_id,
    person_id,
    store_id,
    territory_id,
    account_number,
    modified_date
from {{ source('aw_silver', 'customer') }}
