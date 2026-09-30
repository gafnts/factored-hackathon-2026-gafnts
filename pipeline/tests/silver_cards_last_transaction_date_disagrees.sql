-- Counted, never read: recency comes from the card's transactions (POL-26).
{{ config(severity='warn') }}

select c.product_id
from {{ ref('silver_cards') }} as c
left join (
    select product_id, max(transaction_date) as latest
    from {{ ref('silver_card_transactions') }}
    group by product_id
) as t on c.product_id = t.product_id
where c.last_transaction_date is distinct from t.latest
