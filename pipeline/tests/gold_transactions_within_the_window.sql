-- No gold transaction after the as-of instant or before the 90-day window (ADR-0006, Quality checks).
select t.transaction_id
from {{ ref('gold_transactions') }} as t
cross join {{ ref('gold_metadata') }} as m
where t.transaction_date > m.as_of
    or t.transaction_date <= m.as_of - interval 90 day
