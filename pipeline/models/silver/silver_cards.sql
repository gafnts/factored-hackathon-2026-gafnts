-- Cards opened by the as-of instant, in any status, with their values as delivered. An opening date is read as its
-- midnight, so a card opened on the as-of instant's day counts. Flagged, never corrected (POL-30).
select
    p.product_id,
    p.customer_id,
    {{ trimmed('p.product_type') }} as product_type,
    p.product_number,
    right(trim(p.product_number), 4) as last_four,
    {{ trimmed('p.currency') }} as currency,
    p.current_balance,
    p.credit_limit,
    {{ trimmed('p.product_status') }} as product_status,
    p.opening_date,
    p.expiration_date,
    p.last_transaction_date,
    p.last_updated,
    coalesce(p.expiration_date < k.business_date, false) as past_expiration,
    p.last_updated > k.as_of as updated_after_as_of,
    c.held_out
from {{ ref('bronze_products') }} as p
inner join {{ ref('silver_customers') }} as c on p.customer_id = c.customer_id
cross join {{ ref('silver_clock') }} as k
where {{ trimmed('p.product_type') }} in ('Tarjeta Crédito', 'Tarjeta Débito')
    and p.opening_date <= k.as_of
