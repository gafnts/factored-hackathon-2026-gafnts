-- Transactions on those cards dated by the as-of instant, by transaction_date and never process_date (ADR-0003), with
-- the conflicts POL-30 states: a transaction before its card's opening date, or after its recorded expiration.
select
    t.transaction_id,
    t.customer_id,
    t.product_id,
    t.transaction_date,
    {{ trimmed('t.transaction_type') }} as transaction_type,
    t.amount,
    {{ trimmed('t.currency') }} as currency,
    {{ trimmed('t.channel') }} as channel,
    {{ trimmed('t.merchant_name') }} as merchant_name,
    {{ trimmed('t.merchant_category') }} as merchant_category,
    {{ one_spelling('t.transaction_country') }} as transaction_country,
    {{ trimmed('t.transaction_status') }} as transaction_status,
    {{ trimmed('t.response_code') }} as response_code,
    t.is_fraud,
    t.transaction_date::date < c.opening_date as before_card_opening,
    coalesce(t.transaction_date::date > c.expiration_date, false) as after_card_expiration,
    c.held_out
from {{ ref('bronze_transactions') }} as t
inner join {{ ref('silver_cards') }} as c on t.product_id = c.product_id
cross join {{ ref('silver_clock') }} as k
where t.transaction_date <= k.as_of
