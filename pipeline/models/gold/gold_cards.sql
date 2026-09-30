-- The last four digits in place of the card number (POL-11), and no last_transaction_date (POL-26).
select
    customer_id,
    product_id as card_id,
    product_type,
    last_four,
    currency,
    current_balance,
    credit_limit,
    product_status,
    opening_date,
    expiration_date,
    past_expiration,
    updated_after_as_of
from {{ ref('silver_cards') }}
