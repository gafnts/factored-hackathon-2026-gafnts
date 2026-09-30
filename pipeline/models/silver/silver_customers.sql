-- Customers registered by the as-of instant, with their values as delivered and flagged when updated after it
-- (ADR-0004, State), and the held-out split by ADR-0003's rule (DML-09).
select
    c.customer_id,
    {{ trimmed('c.customer_status') }} as customer_status,
    {{ trimmed('c.country') }} as country,
    {{ trimmed('c.segment') }} as segment,
    c.registration_date,
    c.last_updated,
    c.last_updated > k.as_of as updated_after_as_of,
    md5_number(c.customer_id) % 5 = 0 as held_out
from {{ ref('bronze_customers') }} as c
cross join {{ ref('silver_clock') }} as k
where c.registration_date <= k.as_of
