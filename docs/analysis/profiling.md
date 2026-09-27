# Snapshot profile

Snapshot `b3b8b248f604ef9a`, profiled by `make analysis` with DuckDB 1.5.5. Row counts from 1 to 9 appear as `<10` (SEC-03); [profiling.json](profiling.json) holds the same numbers for code.

## Tables

| Table | Files | Header versions | Rows | Not in the dictionary | Missing |
|---|---|---|---|---|---|
| `branches` | 1 | 1 | 350 | none | none |
| `customers` | 1 | 1 | 150,000 | none | none |
| `products` | 1 | 1 | 400,000 | none | none |
| `service_agents` | 1 | 1 | 1,200 | none | none |
| `marketing_campaigns` | 1 | 1 | 200 | none | none |
| `daily_exchange_rates` | 1 | 1 | 13,164 | none | none |
| `transactions` | 1,097 | 1 | 4,425,008 | none | none |
| `call_center_interactions` | 1,097 | 1 | 686,296 | none | none |
| `call_transcripts` | 1,097 | 1 | 171,321 | none | none |
| `satisfaction_surveys` | 1,097 | 1 | 212,759 | none | none |
| `complaints` | 1,097 | 1 | 67,095 | none | none |
| `digital_events` | 1,097 | 1 | 15,620,994 | none | none |
| `campaign_sends` | 1,083 | 1 | 1,746,801 | none | none |

## Business date

**2026-06-17**: the last day every daily table can be expected to hold at least 99% of its rows, given how late its rows arrived over the rest of the history (ADR-0003). `call_transcripts` has no date of its own and is dated by its interaction.

| Table | Partitions | Missing | Filed under another date | Undated | Events | Next-day events until | 99% arrive within | Last complete day |
|---|---|---|---|---|---|---|---|---|
| `transactions` | 2023-06-17 to 2026-06-17 | 0 | 0 | 0 | 2023-06-17 to 2026-06-18 | 06:00:00 | 0 days | 2026-06-17 |
| `call_center_interactions` | 2023-06-17 to 2026-06-17 | 0 | 0 | 0 | 2023-06-17 to 2026-06-18 | 08:00:00 | 0 days | 2026-06-17 |
| `call_transcripts` | 2023-06-17 to 2026-06-17 | 0 | 0 | 0 | 2023-06-17 to 2026-06-18 | 07:59:59 | 0 days | 2026-06-17 |
| `satisfaction_surveys` | 2023-06-17 to 2026-06-17 | 0 | 0 | 0 | 2023-06-17 to 2026-06-19 | 23:59:58 | 0 days | 2026-06-17 |
| `complaints` | 2023-06-17 to 2026-06-17 | 0 | 0 | 0 | 2023-06-17 to 2026-06-18 | 08:00:00 | 0 days | 2026-06-17 |
| `digital_events` | 2023-06-17 to 2026-06-17 | 0 | 0 | 0 | 2023-06-17 to 2026-06-18 | 06:09:42 | 0 days | 2026-06-17 |
| `campaign_sends` | 2023-07-01 to 2026-06-17 | 0 | 0 | 0 | 2023-07-01 to 2026-06-18 | 06:00:00 | 0 days | 2026-06-17 |

Days from event date to process date. Events dated the day after their process date belong to a processing day that runs past midnight; the column above shows the latest such time of day.

| Table | dated after its process date | same day | 1 day late | 2 to 7 days late | 8 to 30 days late | over 30 days late |
|---|---|---|---|---|---|---|
| `transactions` | 1,106,307 (25.00%) | 3,318,701 (75.00%) | 0 | 0 | 0 | 0 |
| `call_center_interactions` | 228,318 (33.27%) | 457,978 (66.73%) | 0 | 0 | 0 | 0 |
| `call_transcripts` | 57,085 (33.32%) | 114,236 (66.68%) | 0 | 0 | 0 | 0 |
| `satisfaction_surveys` | 169,092 (79.48%) | 43,667 (20.52%) | 0 | 0 | 0 | 0 |
| `complaints` | 22,585 (33.66%) | 44,510 (66.34%) | 0 | 0 | 0 | 0 |
| `digital_events` | 3,930,816 (25.16%) | 11,690,178 (74.84%) | 0 | 0 | 0 | 0 |
| `campaign_sends` | 436,429 (24.98%) | 1,310,372 (75.02%) | 0 | 0 | 0 | 0 |

Rows per event day at the end of the snapshot, as a share of the median over the 28 days before each:

| Day | `transactions` | `call_center_interactions` | `call_transcripts` | `satisfaction_surveys` | `complaints` | `digital_events` | `campaign_sends` |
|---|---|---|---|---|---|---|---|
| 2026-06-04 | 0.95 | 1.02 | 0.87 | 0.97 | 1.35 | 1.20 | 1.17 |
| 2026-06-05 | 0.88 | 0.96 | 0.99 | 1.07 | 1.18 | 0.94 | 1.16 |
| 2026-06-06 | 0.65 | 0.70 | 0.70 | 0.87 | 0.66 | 1.01 | 0.80 |
| 2026-06-07 | 0.54 | 0.62 | 0.61 | 0.63 | 0.50 | 0.95 | 0.60 |
| 2026-06-08 | 0.98 | 1.04 | 1.07 | 0.73 | 0.83 | 1.68 | 0.88 |
| 2026-06-09 | 0.95 | 1.12 | 1.04 | 1.26 | 0.88 | 1.04 | 1.15 |
| 2026-06-10 | 1.11 | 1.09 | 1.13 | 1.19 | 0.98 | 1.09 | 1.19 |
| 2026-06-11 | 1.03 | 1.13 | 1.23 | 1.07 | 1.47 | 2.02 | 1.26 |
| 2026-06-12 | 0.89 | 1.01 | 1.03 | 1.23 | 1.40 | 2.26 | 1.03 |
| 2026-06-13 | 0.77 | 0.67 | 0.68 | 0.84 | 0.57 | 0.90 | 0.72 |
| 2026-06-14 | 0.72 | 0.52 | 0.51 | 0.65 | 0.68 | 0.49 | 0.74 |
| 2026-06-15 | 0.92 | 1.01 | 1.00 | 0.72 | 0.75 | 1.37 | 1.08 |
| 2026-06-16 | 1.08 | 1.18 | 1.27 | 1.31 | 1.18 | 1.06 | 1.12 |
| 2026-06-17 | 1.19 | 0.97 | 0.98 | 1.20 | 1.32 | 0.75 | 1.17 |

Where each processing day ends, by customer country. A time zone would move the cutoff with the country's offset from UTC (Mexico -6, Colombia -5, Argentina -3); a processing day keeps it in place.

| Table | Country | Rows | Same-day events from | Next-day events until |
|---|---|---|---|---|
| `transactions` | Argentina | 880,005 | 06:00:00 | 06:00:00 |
| `transactions` | Colombia | 1,328,572 | 06:00:00 | 06:00:00 |
| `transactions` | México | 2,216,431 | 06:00:00 | 06:00:00 |
| `call_center_interactions` | Argentina | 136,317 | 08:00:01 | 08:00:00 |
| `call_center_interactions` | Colombia | 206,790 | 08:00:00 | 08:00:00 |
| `call_center_interactions` | México | 343,189 | 08:00:00 | 08:00:00 |
| `satisfaction_surveys` | Argentina | 42,475 | 09:10:43 | 23:59:57 |
| `satisfaction_surveys` | Colombia | 64,002 | 09:11:13 | 23:59:51 |
| `satisfaction_surveys` | México | 106,282 | 09:09:27 | 23:59:58 |
| `complaints` | Argentina | 13,336 | 08:00:06 | 07:59:57 |
| `complaints` | Colombia | 20,384 | 08:00:11 | 07:59:57 |
| `complaints` | México | 33,375 | 08:00:01 | 08:00:00 |
| `digital_events` | Argentina | 2,366,476 | 06:00:00 | 06:08:13 |
| `digital_events` | Colombia | 3,578,002 | 06:00:00 | 06:09:34 |
| `digital_events` | México | 5,931,070 | 06:00:00 | 06:08:57 |
| `campaign_sends` | Argentina | 347,022 | 06:00:00 | 06:00:00 |
| `campaign_sends` | Colombia | 527,056 | 06:00:00 | 06:00:00 |
| `campaign_sends` | México | 872,723 | 06:00:00 | 06:00:00 |

## Duplicates

Exact copies repeat another row byte for byte; redelivered rows differ from another only in `process_date`; conflicting versions share a key but differ in content.

| Table | Rows | Exact copies | Redelivered | Conflicting versions | Keys in more than one row | Unique columns repeated |
|---|---|---|---|---|---|---|
| `branches` | 350 | 0 | 0 | 0 | 0 | `branch_code` 0 |
| `customers` | 150,000 | 0 | 0 | 0 | 0 | `document_number` 0 |
| `products` | 400,000 | 0 | 0 | 0 | 0 | `product_number` <10 |
| `service_agents` | 1,200 | 0 | 0 | 0 | 0 | `employee_code` 13 |
| `marketing_campaigns` | 200 | 0 | 0 | 0 | 0 | n/a |
| `daily_exchange_rates` | 13,164 | 0 | 0 | 0 | 0 | n/a |
| `transactions` | 4,425,008 | 0 | 0 | 0 | 0 | n/a |
| `call_center_interactions` | 686,296 | 0 | 0 | 0 | 0 | n/a |
| `call_transcripts` | 171,321 | 0 | 0 | 0 | 0 | n/a |
| `satisfaction_surveys` | 212,759 | 0 | 0 | 0 | 0 | n/a |
| `complaints` | 67,095 | 0 | 0 | 0 | 0 | n/a |
| `digital_events` | 15,620,994 | 0 | 0 | 0 | 0 | n/a |
| `campaign_sends` | 1,746,801 | 0 | 0 | 0 | 0 | n/a |

## References

Rows whose reference points to no row of the referenced table:

| Reference | Rows pointing nowhere |
|---|---|
| `customers.registration_branch_id` | 149,995 (100.00%) |
| `products.customer_id` | 0 |
| `products.opening_branch_id` | 0 |
| `service_agents.assigned_branch_id` | 831 (69.25%) |
| `transactions.product_id` | 0 |
| `transactions.customer_id` | 0 |
| `transactions.branch_id` | 0 |
| `call_center_interactions.customer_id` | 0 |
| `call_center_interactions.agent_id` | 0 |
| `call_transcripts.interaction_id` | 0 |
| `call_transcripts.customer_id` | 0 |
| `call_transcripts.agent_id` | 0 |
| `satisfaction_surveys.interaction_id` | 0 |
| `satisfaction_surveys.customer_id` | 0 |
| `satisfaction_surveys.agent_id` | 0 |
| `complaints.customer_id` | 0 |
| `complaints.affected_product_id` | 0 |
| `complaints.related_branch_id` | 0 |
| `complaints.origin_interaction_id` | 0 |
| `complaints.assigned_agent_id` | 0 |
| `digital_events.customer_id` | 0 |
| `digital_events.product_id` | 0 |
| `campaign_sends.campaign_id` | 0 |
| `campaign_sends.customer_id` | 0 |

## Contact attribution

Whether a contact can be traced to the workflow it was about (ADR-0003):

| Signal | Finding |
|---|---|
| `contact_reason` | 6 distinct values; 686,296 (100.00%) of 686,296 contacts have a reason equal to their `reason_category` |
| `detected_intents` | `consulta_general` |
| `customer_text` in transcripts | 42 distinct texts across 171,321 transcripts; 42 of them appear under every contact reason |
| `mentioned_products` | 548,680 product IDs mentioned; 3,562 (0.65%) exist in `products`; 0 belong to the caller |
| `complaints.origin_interaction_id` | 0 of 67,095 complaints name the interaction they came from |

## Columns

Only columns with an issue are listed. Placeholders are text such as `null` or `N/A` standing in for a missing value; padded values carry leading or trailing spaces; invalid values don't fit the dictionary type.

### branches

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `country` | VARCHAR(50) NOT NULL | 0 | 0 | 0 | 0 | 175 (50.00%) |
| `geographic_zone` | VARCHAR(50) NOT NULL | 0 | 0 | 0 | 0 | 350 (100.00%) |

Values outside the dictionary's list:

- `country`: `México`
- `geographic_zone`: `Urbana`

Boolean spellings:

- `has_atms`: `True`
- `has_teller_windows`: `True`

| Column | Min | Max |
|---|---|---|
| `opening_time` | 08:00:00 | 09:30:00 |
| `closing_time` | 17:00:00 | 20:00:00 |
| `atm_count` | 2 | 8 |
| `teller_window_count` | 3 | 12 |
| `latitude` | -34.6907666 | 25.7817721 |
| `longitude` | -103.4485498 | 0.0999953 |
| `branch_opening_date` | 1990-01-03 | 2023-05-11 |

### customers

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `document_type` | VARCHAR(10) NOT NULL | 0 | 0 | 0 | 0 | 15,062 (10.04%) |
| `email` | VARCHAR(100) | 2,984 (1.99%) | 0 | 0 | 0 | n/a |
| `mobile_phone` | VARCHAR(20) | 4,707 (3.14%) | 0 | 0 | 0 | n/a |
| `landline_phone` | VARCHAR(20) | 75,053 (50.04%) | 0 | 0 | 0 | n/a |
| `address` | VARCHAR(200) | 7,370 (4.91%) | 0 | 0 | 0 | n/a |
| `country` | VARCHAR(50) NOT NULL | 0 | 0 | 0 | 0 | 74,907 (49.94%) |
| `postal_code` | VARCHAR(10) | 15,044 (10.03%) | 0 | 0 | 0 | n/a |
| `detected_accent` | VARCHAR(50) | 44,817 (29.88%) | 0 | 0 | 0 | 0 |
| `credit_score` | INTEGER | 22,492 (14.99%) | 0 | 0 | 0 | n/a |
| `estimated_monthly_income` | DECIMAL(12,2) | 30,033 (20.02%) | 0 | 0 | 0 | n/a |
| `occupation` | VARCHAR(100) | 15,039 (10.03%) | 0 | 0 | 0 | n/a |
| `marital_status` | VARCHAR(20) | 11,955 (7.97%) | 0 | 0 | 0 | n/a |
| `education_level` | VARCHAR(50) | 17,952 (11.97%) | 0 | 0 | 0 | n/a |

Values outside the dictionary's list:

- `document_type`: `Pasaporte`
- `country`: `México`

Boolean spellings:

- `accepts_marketing`: `False`, `True`

| Column | Min | Max |
|---|---|---|
| `date_of_birth` | 1942-07-07 | 2005-06-21 |
| `credit_score` | 422 | 850 |
| `estimated_monthly_income` | 5100.28 | 111895075.15 |
| `registration_date` | 2018-06-18 01:21:11 | 2026-06-17 23:53:29 |
| `last_updated` | 2018-06-18 15:09:31 | 2027-06-15 19:35:27 |

### products

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `credit_limit` | DECIMAL(15,2) | 274,683 (68.67%) | 0 | 0 | 0 | n/a |
| `interest_rate` | DECIMAL(5,2) | 40,066 (10.02%) | 0 | 0 | 0 | n/a |
| `expiration_date` | DATE | 266,839 (66.71%) | 0 | 0 | 0 | n/a |
| `days_past_due` | INTEGER | 274,650 (68.66%) | 0 | 0 | 0 | n/a |
| `last_transaction_date` | TIMESTAMP | 94,277 (23.57%) | 0 | 0 | 0 | n/a |

Boolean spellings:

- `has_linked_app`: `False`, `True`

| Column | Min | Max |
|---|---|---|
| `current_balance` | 0.00 | 881511545.61 |
| `credit_limit` | 1000.33 | 599984205.95 |
| `interest_rate` | 0.00 | 45.00 |
| `opening_date` | 2018-06-18 | 2026-06-17 |
| `expiration_date` | 2021-06-17 | 2031-06-16 |
| `days_past_due` | 0 | 180 |
| `last_transaction_date` | 2018-06-21 17:07:15 | 2026-06-17 23:17:43 |
| `last_updated` | 2018-06-20 05:21:54 | 2027-06-15 02:26:58 |

### service_agents

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `phone` | VARCHAR(20) | 69 (5.75%) | 0 | 0 | 0 | n/a |
| `assigned_branch_id` | VARCHAR(20) | 367 (30.58%) | 0 | 0 | 0 | n/a |
| `specialty` | VARCHAR(100) | 476 (39.67%) | 0 | 0 | 0 | n/a |
| `avg_csat` | DECIMAL(3,2) | 134 (11.17%) | 0 | 0 | 0 | n/a |
| `total_monthly_interactions` | INTEGER | 111 (9.25%) | 0 | 0 | 0 | n/a |

| Column | Min | Max |
|---|---|---|
| `hire_date` | 2013-06-20 | 2026-03-17 |
| `avg_csat` | 3.50 | 5.00 |
| `total_monthly_interactions` | 100 | 800 |

### marketing_campaigns

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `description` | TEXT | 39 (19.50%) | 0 | 0 | 0 | n/a |
| `promoted_product` | VARCHAR(50) | 22 (11.00%) | 0 | 0 | 0 | n/a |
| `target_segment` | VARCHAR(50) | 79 (39.50%) | 0 | 0 | 0 | n/a |
| `target_country` | VARCHAR(50) | 111 (55.50%) | 0 | 0 | 0 | n/a |
| `budget` | DECIMAL(12,2) | 31 (15.50%) | 0 | 0 | 0 | n/a |
| `expected_conversion_rate` | DECIMAL(5,2) | 14 (7.00%) | 0 | 0 | 0 | n/a |

| Column | Min | Max |
|---|---|---|
| `start_date` | 2023-07-01 | 2026-06-14 |
| `end_date` | 2023-08-11 | 2026-08-20 |
| `budget` | 6355.31 | 499954.38 |
| `expected_conversion_rate` | 0.55 | 14.69 |

### daily_exchange_rates

No column issues.

| Column | Min | Max |
|---|---|---|
| `date` | 2023-06-17 | 2026-06-17 |
| `exchange_rate` | 0.000245 | 4079.944006 |
| `buy_rate` | 0.000241 | 4057.980570 |
| `sell_rate` | 0.000246 | 4138.591967 |

### transactions

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `transaction_category` | VARCHAR(50) | 2,693,520 (60.87%) | 0 | 0 | 0 | 0 |
| `amount_usd` | DECIMAL(15,2) | 2,537,456 (57.34%) | 0 | 0 | 0 | n/a |
| `branch_id` | VARCHAR(20) | 3,037,076 (68.63%) | 0 | 0 | 0 | n/a |
| `merchant_name` | VARCHAR(150) | 3,395,774 (76.74%) | 0 | 0 | 0 | n/a |
| `merchant_category` | VARCHAR(50) | 3,396,215 (76.75%) | 0 | 0 | 0 | n/a |
| `transaction_city` | VARCHAR(100) | 442,611 (10.00%) | 0 | 0 | 0 | n/a |
| `response_code` | VARCHAR(10) | 221,033 (5.00%) | 0 | 0 | 0 | n/a |
| `fraud_score` | DECIMAL(5,2) | 885,157 (20.00%) | 0 | 0 | 0 | n/a |
| `latitude` | DECIMAL(10,7) | 3,567,680 (80.63%) | 0 | 0 | 0 | n/a |
| `longitude` | DECIMAL(10,7) | 3,567,715 (80.63%) | 0 | 0 | 0 | n/a |

Boolean spellings:

- `is_fraud`: `False`, `True`

| Column | Min | Max |
|---|---|---|
| `transaction_date` | 2023-06-17 06:01:30 | 2026-06-18 05:59:41 |
| `process_date` | 2023-06-17 | 2026-06-17 |
| `amount` | 5.00 | 39999828.48 |
| `amount_usd` | 5.00 | 9999.96 |
| `fraud_score` | 0.00 | 99.99 |
| `latitude` | -35.6036984 | 5.7109985 |
| `longitude` | -75.0720969 | 0.9999900 |

### call_center_interactions

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `channel` | VARCHAR(30) NOT NULL | 0 | 0 | 0 | 0 | 3,395 (0.49%) |
| `reason_category` | VARCHAR(50) NOT NULL | 0 | 0 | 0 | 0 | 686,296 (100.00%) |
| `duration_seconds` | INTEGER | 96,234 (14.02%) | 0 | 0 | 0 | n/a |
| `wait_time_seconds` | INTEGER | 205,618 (29.96%) | 0 | 0 | 0 | n/a |
| `detected_sentiment` | VARCHAR(20) | 0 | 0 | 0 | 0 | 226,584 (33.02%) |
| `customer_detected_accent` | VARCHAR(50) | 204,750 (29.83%) | 0 | 0 | 0 | n/a |
| `agent_used_accent` | VARCHAR(50) | 204,750 (29.83%) | 0 | 0 | 0 | n/a |
| `mentioned_products` | VARCHAR(200) | 411,955 (60.03%) | 0 | 0 | 0 | n/a |

Values outside the dictionary's list:

- `channel`: `Web`
- `reason_category`: `Comercial`, `Producto`, `Queja`, `Retención`, `Transaccional`, `Técnico`
- `detected_sentiment`: `Muy Negativo`, `Muy Positivo`, `Negativo`, `Positivo`

Boolean spellings:

- `was_resolved`: `False`, `True`
- `requires_followup`: `False`, `True`
- `was_escalated`: `False`, `True`
- `has_transcript`: `False`, `True`
- `has_recording`: `False`, `True`

| Column | Min | Max |
|---|---|---|
| `interaction_date` | 2023-06-17 08:03:26 | 2026-06-18 07:58:13 |
| `process_date` | 2023-06-17 | 2026-06-17 |
| `duration_seconds` | 30 | 1204 |
| `wait_time_seconds` | 0 | 424 |
| `sentiment_score` | -1.00 | 1.00 |

### call_transcripts

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `detected_accent` | VARCHAR(50) | 63,083 (36.82%) | 0 | 0 | 0 | n/a |
| `accent_confidence` | DECIMAL(3,2) | 17,141 (10.01%) | 0 | 0 | 0 | n/a |
| `detected_keywords` | VARCHAR(500) | 8,797 (5.13%) | 0 | 0 | 0 | n/a |
| `mentioned_entities` | TEXT | 17,164 (10.02%) | 0 | 0 | 0 | n/a |
| `detected_intents` | VARCHAR(300) | 8,457 (4.94%) | 0 | 0 | 0 | n/a |
| `audio_quality` | VARCHAR(20) | 8,638 (5.04%) | 0 | 0 | 0 | 0 |
| `duration_seconds` | INTEGER NOT NULL | 24,029 (14.03%) | 0 | 0 | 0 | n/a |

| Column | Min | Max |
|---|---|---|
| `process_date` | 2023-06-17 | 2026-06-17 |
| `accent_confidence` | 0.75 | 0.99 |
| `duration_seconds` | 30 | 1151 |

### satisfaction_surveys

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `nps_category` | VARCHAR(20) | 152,365 (71.61%) | 0 | 0 | 0 | 0 |
| `question_1_text` | TEXT | 91,456 (42.99%) | 0 | 0 | 0 | n/a |
| `question_1_response` | INTEGER | 91,389 (42.95%) | 0 | 0 | 0 | n/a |
| `question_2_text` | TEXT | 131,388 (61.75%) | 0 | 0 | 0 | n/a |
| `question_2_response` | INTEGER | 131,263 (61.70%) | 0 | 0 | 0 | n/a |
| `question_3_text` | TEXT | 172,615 (81.13%) | 0 | 0 | 0 | n/a |
| `question_3_response` | INTEGER | 172,656 (81.15%) | 0 | 0 | 0 | n/a |
| `open_comments` | TEXT | 111,563 (52.44%) | 0 | 0 | 0 | n/a |
| `comment_sentiment` | VARCHAR(20) | 111,502 (52.41%) | 0 | 0 | 0 | n/a |
| `campaign_response_rate` | DECIMAL(5,2) | 32,037 (15.06%) | 0 | 0 | 0 | n/a |

| Column | Min | Max |
|---|---|---|
| `survey_date` | 2023-06-17 09:29:20 | 2026-06-19 06:54:58 |
| `process_date` | 2023-06-17 | 2026-06-17 |
| `main_score` | 1 | 7 |
| `question_1_response` | 1 | 5 |
| `question_2_response` | 1 | 5 |
| `question_3_response` | 1 | 5 |
| `response_time_hours` | 1.01 | 35.97 |
| `campaign_response_rate` | 15.00 | 45.00 |

### complaints

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `subcategory` | VARCHAR(100) | 6,698 (9.98%) | 0 | 0 | 0 | n/a |
| `affected_product_id` | VARCHAR(20) | 22,525 (33.57%) | 0 | 0 | 0 | n/a |
| `related_branch_id` | VARCHAR(20) | 47,917 (71.42%) | 0 | 0 | 0 | n/a |
| `origin_interaction_id` | VARCHAR(30) | 67,095 (100.00%) | 0 | 0 | 0 | n/a |
| `claimed_amount` | DECIMAL(15,2) | 45,344 (67.58%) | 0 | 0 | 0 | n/a |
| `currency` | VARCHAR(3) | 45,319 (67.54%) | 0 | 0 | 0 | 0 |
| `assigned_agent_id` | VARCHAR(20) | 23,115 (34.45%) | 0 | 0 | 0 | n/a |
| `assignment_date` | TIMESTAMP | 23,128 (34.47%) | 0 | 0 | 0 | n/a |
| `first_response_date` | TIMESTAMP | 26,242 (39.11%) | 0 | 0 | 0 | n/a |
| `resolution_date` | TIMESTAMP | 51,746 (77.12%) | 0 | 0 | 0 | n/a |
| `closing_date` | TIMESTAMP | 64,614 (96.30%) | 0 | 0 | 0 | n/a |
| `resolution_days` | INTEGER | 51,732 (77.10%) | 0 | 0 | 0 | n/a |
| `resolution` | TEXT | 51,785 (77.18%) | 0 | 0 | 0 | n/a |
| `compensation_granted` | DECIMAL(15,2) | 62,454 (93.08%) | 0 | 0 | 0 | n/a |
| `resolution_satisfaction` | INTEGER | 64,611 (96.30%) | 0 | 0 | 0 | n/a |

Boolean spellings:

- `sla_breached`: `False`, `True`
- `is_repeat_complainer`: `False`, `True`

| Column | Min | Max |
|---|---|---|
| `creation_date` | 2023-06-17 08:07:05 | 2026-06-18 07:56:52 |
| `process_date` | 2023-06-17 | 2026-06-17 |
| `claimed_amount` | 50.27 | 4999.93 |
| `assignment_date` | 2023-06-17 22:26:12 | 2026-06-19 03:56:52 |
| `first_response_date` | 2023-06-18 03:37:40 | 2026-06-20 22:42:19 |
| `resolution_date` | 2023-06-20 07:10:42 | 2026-07-18 06:07:57 |
| `closing_date` | 2023-06-26 11:38:44 | 2026-07-18 22:15:16 |
| `resolution_days` | 1 | 30 |
| `compensation_granted` | 10.15 | 499.98 |
| `resolution_satisfaction` | 1 | 5 |

### digital_events

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `customer_id` | VARCHAR(20) | 3,745,446 (23.98%) | 0 | 0 | 0 | n/a |
| `platform` | VARCHAR(30) | 780,527 (5.00%) | 0 | 0 | 0 | 0 |
| `browser` | VARCHAR(50) | 9,687,736 (62.02%) | 0 | 0 | 0 | n/a |
| `app_version` | VARCHAR(20) | 6,714,416 (42.98%) | 0 | 0 | 0 | n/a |
| `page_url` | VARCHAR(300) | 780,394 (5.00%) | 0 | 0 | 0 | n/a |
| `page_title` | VARCHAR(200) | 779,824 (4.99%) | 0 | 0 | 0 | n/a |
| `action` | VARCHAR(100) | 1,561,432 (10.00%) | 0 | 0 | 0 | n/a |
| `element_id` | VARCHAR(100) | 2,343,244 (15.00%) | 0 | 0 | 0 | n/a |
| `product_id` | VARCHAR(20) | 14,180,656 (90.78%) | 0 | 0 | 0 | n/a |
| `event_value` | DECIMAL(15,2) | 14,826,484 (94.91%) | 0 | 0 | 0 | n/a |
| `duration_seconds` | INTEGER | 9,946,209 (63.67%) | 0 | 0 | 0 | n/a |
| `ip_address` | VARCHAR(45) | 780,855 (5.00%) | 0 | 0 | 0 | n/a |
| `ip_city` | VARCHAR(100) | 4,370,476 (27.98%) | 0 | 0 | 0 | n/a |
| `referrer` | VARCHAR(300) | 14,573,469 (93.29%) | 0 | 0 | 0 | n/a |
| `utm_source` | VARCHAR(100) | 14,781,949 (94.63%) | 0 | 0 | 0 | n/a |
| `utm_medium` | VARCHAR(100) | 14,781,860 (94.63%) | 0 | 0 | 0 | n/a |
| `utm_campaign` | VARCHAR(100) | 14,782,077 (94.63%) | 0 | 0 | 0 | n/a |

Boolean spellings:

- `is_mobile`: `False`, `True`

| Column | Min | Max |
|---|---|---|
| `event_date` | 2023-06-17 06:02:03 | 2026-06-18 06:04:05 |
| `process_date` | 2023-06-17 | 2026-06-17 |
| `event_value` | 10.01 | 4999.98 |
| `duration_seconds` | 5 | 300 |

### campaign_sends

| Column | Type | Nulls | Placeholders | Padded | Invalid | Outside documented values |
|---|---|---|---|---|---|---|
| `template_used` | VARCHAR(100) | 175,218 (10.03%) | 0 | 0 | 0 | n/a |
| `subject` | VARCHAR(200) | 1,188,342 (68.03%) | 0 | 0 | 0 | n/a |
| `was_opened` | BOOLEAN | 484,229 (27.72%) | 0 | 0 | 0 | n/a |
| `open_date` | TIMESTAMP | 1,259,492 (72.10%) | 0 | 0 | 0 | n/a |
| `click_date` | TIMESTAMP | 1,649,008 (94.40%) | 0 | 0 | 0 | n/a |
| `click_count` | INTEGER | 1,649,008 (94.40%) | 0 | 0 | 0 | n/a |
| `conversion_date` | TIMESTAMP | 1,737,002 (99.44%) | 0 | 0 | 0 | n/a |
| `conversion_value` | DECIMAL(15,2) | 1,737,002 (99.44%) | 0 | 0 | 0 | n/a |
| `open_device` | VARCHAR(30) | 1,308,424 (74.90%) | 0 | 0 | 0 | n/a |
| `open_country` | VARCHAR(50) | 1,308,278 (74.90%) | 0 | 0 | 0 | n/a |
| `failure_reason` | VARCHAR(200) | 1,647,204 (94.30%) | 0 | 0 | 0 | n/a |
| `send_cost` | DECIMAL(10,4) | 262,083 (15.00%) | 0 | 0 | 0 | n/a |

Boolean spellings:

- `was_delivered`: `False`, `True`
- `was_opened`: `False`, `True`
- `was_clicked`: `False`, `True`
- `had_conversion`: `False`, `True`

| Column | Min | Max |
|---|---|---|
| `send_date` | 2023-07-01 06:00:42 | 2026-06-18 05:59:53 |
| `process_date` | 2023-07-01 | 2026-06-17 |
| `open_date` | 2023-07-01 07:44:22 | 2026-06-25 03:30:02 |
| `click_date` | 2023-07-01 21:57:26 | 2026-06-24 23:51:59 |
| `click_count` | 1 | 5 |
| `conversion_date` | 2023-07-03 12:56:27 | 2026-06-26 08:26:49 |
| `conversion_value` | 100.88 | 4999.75 |
| `send_cost` | 0.0001 | 0.3000 |

## Languages

| `call_transcripts.detected_language` | Rows |
|---|---|
| `es` | 171,321 (100.00%) |
