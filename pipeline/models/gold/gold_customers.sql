-- The customer's status stays in the data: the tools return only whether the customer is served in full (POL-12).
select
    customer_id,
    customer_status,
    country,
    updated_after_as_of
from {{ ref('silver_customers') }}
