-- A transaction's customer is its card's, since gold files it under that customer's partition (ADR-0004, Stores).
select t.transaction_id
from {{ ref('silver_card_transactions') }} as t
inner join {{ ref('silver_cards') }} as c on t.product_id = c.product_id
where t.customer_id <> c.customer_id
