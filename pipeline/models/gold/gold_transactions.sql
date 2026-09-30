-- The 90 days (90 × 24 hours) that end at the as-of instant, by each transaction's own timestamp (POL-25); no amount_usd
-- or fraud_score (POL-20, POL-40).
select
    t.customer_id,
    t.transaction_id,
    t.product_id as card_id,
    t.transaction_date,
    t.transaction_type,
    t.amount,
    t.currency,
    t.channel,
    t.merchant_name,
    t.merchant_category,
    t.transaction_country,
    t.transaction_status,
    t.response_code,
    t.is_fraud,
    t.before_card_opening,
    t.after_card_expiration
from {{ ref('silver_card_transactions') }} as t
cross join {{ ref('silver_clock') }} as k
where t.transaction_date > k.as_of - interval 90 day
