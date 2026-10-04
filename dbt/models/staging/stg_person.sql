-- person_type: IN = individual (retail) customer, SC = store contact, EM = employee, SP = sales person,
-- VC = vendor contact, GC = general contact.
select
    business_entity_id as person_id,
    person_type,
    title,
    first_name,
    middle_name,
    last_name,
    suffix,
    modified_date
from {{ source('aw_silver', 'person') }}
