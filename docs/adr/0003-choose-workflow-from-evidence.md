# ADR-0003: Choose the workflow from evidence

> [!IMPORTANT]
> **The snapshot looks like a bank but doesn't behave like one.** Its tables fit together (purchases sit on cards, handle time varies with the contact reason), but the values that would carry a bank's behavior were generated without regard to the rest of the record:
>
> - `is_fraud` and `days_past_due` are independent of every field E2 reads, and `fraud_score` is drawn from `is_fraud`: a copy of the label, not a model.
> - Contacts can't be tied to a workflow: six coarse reasons, transcripts templated independently of the reason, product mentions that point at random products.
> - Records conflict: about half of all cards, active ones included, are past their expiration date, and the active ones still transact.
> - Missing values, about 5% of each core field, are injected at random.
>
> **So:** the workflow is chosen on feasibility, not on demand or learnable signal. Nothing learns from the bank's labels; the learned component is a router of customer requests, with labels from our policy. Expected outcomes come from our policy applied to the frozen state. `is_fraud` is read as the bank's own flag, never as the truth of a customer's claim, so a charge the customer doesn't recognize goes to review either way. Tools surface conflicting records instead of resolving them, and every gap is reported as a limitation (SCP-07).
>
> **The choice is card support.** With E2 set aside (no candidate can pass it on this data), it is the only candidate that passes F1, F2, and E1: its core fields are at least 94.95% populated, and 32,588 customers are in its normal-path state. That shows card support is feasible, not that the others are infeasible or that customers need it most, and it was our working hypothesis (see [Revisit](#revisit)). Its normal path also runs the whole loop the brief asks for: explain verified facts, act on confirmation (a card block in the sandbox), verify the result, and hand off with evidence.

## Status

Accepted (2026-09-27): card support (see [Result](#result)). The rule was revised three times before acceptance: once before any gate ran, fixed by the table-level [data quality profile](../analysis/profiling.md), which showed that agent time and customer pain can't be measured (see Context); once on how each gate is measured (see Measurement); and once with every gate result in view, as the rule requires (see [Revisit](#revisit)), since no candidate passed all four. Acceptance added the result and its consequences for the evaluation; the rule is unchanged since the revisit.

Amended as built, the correction applied in the section it names:

- 2026-09-29, by [ADR-0004](0004-agent-architecture-on-agentcore.md#state-a-frozen-master-snapshot-with-an-event-cutoff): the sentence in [Dates](#dates) that every table shows the bank at the same moment holds for event tables only.

## Context

The system serves one focused workflow (SCP-01). The brief names four examples: account or payment inquiries, card-service support, transaction-dispute intake, and credit-product information and eligibility. They aren't tracks, and building more than one earns nothing. The choice has to come from the supplied data, in an analysis anyone can rerun (PRB-01 to PRB-05).

Five forces shape how the choice is made:

- **Everything downstream depends on it.** Silver and gold tables, tools, policy, personas, and evaluation cases are all built for one workflow, so a late change would redo most of the build.
- **We already have a favorite.** Our working hypothesis, card support handing off to dispute intake, is untested. A rule written after the numbers could be bent to confirm it.
- **This snapshot can't say which workflow a contact was about.** The profile's [contact attribution](../analysis/profiling.md#contact-attribution) section shows why:
  - `contact_reason` holds six values, each identical to its `reason_category`: Comercial, Producto, Queja, Retención, Transaccional, Técnico. None maps to one workflow.
  - Transcripts don't depend on the contact: their customer text comes from two openings (a credit card balance and a savings balance) with stock closings, and every variant appears under all six reasons. `detected_intents` holds a single value.
  - The product IDs in `mentioned_products` are random: almost none exist, and none belong to the caller.
  - No complaint records the interaction it came from.
- **The state tables are rich.** Accounts, cards, transactions, customers, and complaints carry the fields a workflow's tools and policy would read, so whether the data can support each workflow is measurable even though demand for it isn't.
- **Git can prove the order.** If this revision is committed before the gates run, the history shows the rule came first.

## Decision

Choose the workflow in two steps: gates computed by `make analysis` on snapshot `b3b8b248f604ef9a`, then a written judgment among the workflows that pass, on criteria fixed here, in order. Contact demand per workflow isn't scored, because this snapshot can't attribute contacts to workflows. Reports publish aggregates only, with counts under 10 suppressed (SEC-03).

### Candidates

The four workflows the brief names. A candidate may end by handing off to another workflow (card support routing a customer to dispute intake, for example) the same way it hands off to a human: with a structured payload (CTL-05), without performing that workflow's steps. Its gates are judged on its own fields and states; anything past the handoff is out of scope (SCP-01).

### Dates

The business date is the last day for which every daily table can be expected to hold at least 99% of its rows, given how late rows arrived over the rest of the history. Each processing day runs past midnight, to a fixed cutoff the next morning.

Everything is read as of one instant: the end of the business date's processing day, taken as the earliest of the daily tables' cutoffs on the following morning (06:00 in the profile, set by transactions and campaign sends). Every event table then shows the bank at the same moment, with rows dated after it ignored; customers and products carry no history, so they show their values as delivered, flagged when updated after the as-of instant ([ADR-0004](0004-agent-architecture-on-agentcore.md#state-a-frozen-master-snapshot-with-an-event-cutoff)). A window such as "the 30 days before the business date" is the 30 × 24 hours ending at the as-of instant, counted by each event's own timestamp, never by `process_date`.

### Gates

A candidate must pass all four.

| Gate | Passes when |
|---|---|
| F1: fields | The fields its core tools read (table below) are at least 90% populated in the rows those tools would read |
| F2: state | At least 100 customers are, at the as-of instant, in the state its normal path needs (table below) |
| E1: reference outcomes | Its expected outcomes can be written as deterministic rules over the frozen state; the ADR sketches three such rules and the fields they read |
| E2: learned component | A label that comes from the supplied data, never one we write, shows signal on held-out customers (DML-07 to DML-09): a logistic regression on fields recorded with the event reaches a held-out ROC AUC whose 95% bootstrap interval lies above 0.5, with training and held-out customers kept apart |

Fields and states, taken from the data dictionary before looking at the data:

| Candidate | Core fields | Normal-path state |
|---|---|---|
| Account and payment inquiries | `products`: `product_type`, `product_status`, `current_balance`, `currency`; `transactions`: `transaction_date`, `amount`, `transaction_type`, `transaction_status`, `merchant_name`, `channel` | An active checking or savings account with a transaction in the 30 days before the business date |
| Card support | `products`: `product_type`, `product_status`, `credit_limit`, `current_balance`, `expiration_date`; `transactions`: `transaction_status`, `response_code`, `is_fraud`, `merchant_name`, `channel`, `transaction_country` | An active credit or debit card with a transaction in the 30 days before the business date |
| Transaction-dispute intake | `transactions`: `transaction_date`, `amount`, `currency`, `transaction_status`, `merchant_name`, `is_fraud`, `fraud_score`; `complaints`: `case_type`, `claimed_amount`, `status` | An approved purchase in the 60 days before the business date |
| Credit information and eligibility | `customers`: `credit_score`, `estimated_monthly_income`, `segment`, `customer_status`; `products`: `product_type`, `credit_limit`, `interest_rate`, `days_past_due` | An active customer with `credit_score` and `estimated_monthly_income` populated |

Labels for E2, also from the dictionary. The features never include `fraud_score`, `response_code` or `transaction_status`, which may already encode the answer: the last two record the bank's own authorization decision, and `fraud_score` is drawn from `is_fraud` itself (see [Revisit](#revisit)), so it is no model and no baseline either.

| Candidate | Label | What the learned component would do |
|---|---|---|
| Account and payment inquiries | None in the dictionary | Nothing, so the candidate fails E2 |
| Card support | `is_fraud` on card transactions | Score a transaction as suspicious, to offer a card block or hand off |
| Transaction-dispute intake | `is_fraud` on the transactions a customer could dispute | Triage a dispute as likely fraud or a merchant disagreement |
| Credit information and eligibility | `days_past_due` of 30 or more on credit products | Estimate repayment risk, kept apart from eligibility policy (CRD-01) |

If exactly one candidate passes, it wins. If none does, the gates are revisited in writing before anything else.

### Measurement

Fixed before any gate ran, so that no choice of rows, features, or split is made while looking at a result.

**Terms.** The snapshot names products in Spanish: checking and savings accounts are `Cuenta Corriente` and `Cuenta Ahorro`, credit and debit cards `Tarjeta Crédito` and `Tarjeta Débito`, and the credit products are `Tarjeta Crédito`, `Préstamo Personal`, and `Préstamo Hipotecario`. Active means a `product_status` or `customer_status` of `Active`. An approved purchase is a `Purchase` whose `transaction_status` is `Approved`. A dispute complaint is one in a category the judgment's mapping assigns to dispute intake (Transactions and Fees). Only rows that exist at the as-of instant count: products opened, customers registered, transactions made, and complaints created by then.

**F1** measures each core field on its own, over the rows its tools would read:

| Candidate | Rows |
|---|---|
| Account and payment inquiries | Checking and savings accounts, and their transactions in the 30 days before the as-of instant |
| Card support | Credit and debit cards, and their transactions in the 30 days before the as-of instant |
| Transaction-dispute intake | Approved purchases in the 60 days before the as-of instant, and dispute complaints |
| Credit information and eligibility | Customers, and credit products |

Within those rows, a field the dictionary documents for some rows only is measured on those: `credit_limit` "for credit products" (credit cards, for card support), `days_past_due` "for credits", and `merchant_name` "for purchases". `claimed_amount`, documented "if applicable", applies to every dispute complaint, since each disputes a charge. The dictionary documents `expiration_date` "for term products", but card support reads it on cards, so it is measured on cards: no field leaves the committed lists. A field with no rows to measure fails.

**F2** counts each customer once, however many qualifying products or transactions they hold.

**E1** passes when three rules can be written that read only fields the snapshot holds, through references it holds, and give one expected outcome for any state of those fields. The sketches cover the normal path, a request the workflow must decline or can't confirm, and a handoff. Their thresholds and wording become the team-written policy, labeled synthetic (SEC-02), for the workflow that wins.

| Candidate | Rule | Reads |
|---|---|---|
| Account and payment inquiries | A checking or savings account of the signed-in customer is reported with its `current_balance` in its `currency`, and with its transactions of the 30 days before the as-of instant, newest first | `products`: `customer_id`, `product_type`, `current_balance`, `currency`; `transactions`: `product_id`, `transaction_date`, `amount`, `transaction_type`, `transaction_status`, `merchant_name`, `channel` |
| | A movement the customer describes by amount and date that matches no transaction on the account in that window is reported as not found; none is inferred | `transactions`: `amount`, `transaction_date` |
| | A `Payment` the customer says went through, but whose `transaction_status` is `Declined` or `Reversed`, is handed off with its recorded fields as verified facts; a `Pending` one is reported as not yet posted | `transactions`: `transaction_type`, `transaction_status` |
| Card support | A card of the signed-in customer is reported with its `product_status`; a credit card also with its `credit_limit` minus its `current_balance` as available credit | `products`: `customer_id`, `product_type`, `product_status`, `credit_limit`, `current_balance` |
| | A `Declined` card transaction is explained by its `response_code`, read with its ISO 8583 meaning (05 do not honor, 14 invalid card number, 51 insufficient funds, 54 expired card); a missing or unlisted code gets no explanation, and the answer says so | `transactions`: `transaction_status`, `response_code` |
| | A card is blocked only if it is `Active`, belongs to the signed-in customer, and the customer confirms; the sandbox then shows it `Blocked`. A block over a transaction marked `is_fraud` also hands off to dispute intake with that transaction | `products`: `product_status`; `transactions`: `is_fraud`, `merchant_name`, `channel`, `transaction_country` |
| Transaction-dispute intake | A transaction can be disputed only if it belongs to the signed-in customer, is an approved purchase, and falls in the 60 days before the as-of instant; otherwise no case is opened, and the answer names the condition that failed | `transactions`: `customer_id`, `transaction_type`, `transaction_status`, `transaction_date` |
| | A case records the transaction's `transaction_date`, `amount`, `currency`, and `merchant_name` as read from the transaction, never from the conversation; an amount the customer states differently goes into the handoff as an unresolved question | `transactions`: `transaction_id`, `transaction_date`, `amount`, `currency`, `merchant_name` |
| | A disputed transaction marked `is_fraud` takes the fraud route (card block offered, human review); any other takes the merchant-dispute route | `transactions`: `is_fraud` |
| Credit information and eligibility | A credit product of the signed-in customer is reported with its `credit_limit`, `interest_rate`, and `days_past_due` as recorded; no rate or limit is quoted for a product the customer doesn't hold | `products`: `customer_id`, `product_type`, `credit_limit`, `interest_rate`, `days_past_due` |
| | A simulated eligibility outcome is positive only if `customer_status` is `Active`, `credit_score` and `estimated_monthly_income` meet the policy's thresholds for the customer's `segment`, and no credit product has `days_past_due` of 30 or more; a negative outcome names the condition that failed (CRD-02) | `customers`: `customer_status`, `segment`, `credit_score`, `estimated_monthly_income`; `products`: `days_past_due` |
| | A missing `credit_score` or `estimated_monthly_income`, or a score within the policy's margin of its threshold, gets no outcome and goes to human review (CRD-04) | `customers`: `credit_score`, `estimated_monthly_income` |

A rule that finds an earlier dispute of the same transaction can't be written: complaints carry no transaction reference.

**E2** fits one model per candidate with a label:

| Candidate | One row per | Label |
|---|---|---|
| Card support | Card transaction | `is_fraud` |
| Transaction-dispute intake | Approved purchase | `is_fraud` |
| Credit information and eligibility | Credit product with `days_past_due` populated | `days_past_due` of 30 or more |

Because complaints carry no transaction reference, the transaction a dispute is about can't be identified. The dispute label is therefore `is_fraud` on the transactions a customer could dispute, rows that overlap card support's.

- **Transaction features:** `transaction_type`, `transaction_category`, `channel`, `merchant_category`, `currency`, the logarithm of `amount`, whether `transaction_country` differs from the customer's `country`, the hour and weekday of `transaction_date`, and the `product_type` it was made on.
- **Credit features:** the customer's `segment`, `country`, `credit_score`, the logarithm of `estimated_monthly_income`, and age and months since registration at the business date; the product's `product_type`, `interest_rate`, the logarithm of `credit_limit`, and months since `opening_date`. Never `current_balance`, `product_status`, `last_transaction_date`, or `last_updated`, which a missed payment can change. Customers and products carry no history, so every feature is read as the snapshot holds it, and `credit_score` may already reflect the delinquency it is asked to predict; the report says so.
- **Missing values:** a missing category is a value of its own; a missing number takes the training median plus a flag.
- **Split:** a customer is held out when the MD5 of their `customer_id`, read as an integer, is divisible by 5 (about a fifth of customers), so all of a customer's rows fall on one side.
- **Model:** logistic regression with an L2 penalty (C = 1) on numbers standardized over the training rows, without tuning: E2 asks whether the label carries signal, not how much a tuned model finds.
- **Interval:** a 95% percentile bootstrap of the held-out ROC AUC over 1,000 resamples of held-out customers, not rows, since a customer's rows move together; the seed is fixed and reported. E2 passes when the interval's lower end is above 0.5.
- **Reported alongside:** the point estimate; rows, customers, and positives on each side; and, for `is_fraud`, the held-out ROC AUC of `fraud_score` where it is populated, as context on how closely it tracks the label, outside the gate.

### Judgment

Among the candidates that pass, the choice follows these criteria in this order. A later criterion decides only when the earlier ones leave candidates level, and each is argued in writing in this ADR:

1. **Evaluation depth.** How many of the evaluation situations that depend on the workflow the frozen state can supply with real records: the normal path (SCP-03), an ambiguous or unsupported request (SCP-04), a case needing a human (SCP-05), and incorrect or missing data (EVL-02). The rest (expired sessions, unauthorized access, prompt injection, tool failures, multilingual ambiguity) don't depend on the workflow.
2. **Risk.** The harm a wrong answer or action can do and how reversible it is, including fraud exposure; credit also carries CRD-01 to CRD-04.
3. **Attributable demand.** Only complaints can be attributed, by category, with this mapping:

   | Category / subcategory | Candidate |
   |---|---|
   | Transactions / Cargo no reconocido | Transaction-dispute intake |
   | Fees / Cobro indebido | Transaction-dispute intake |
   | Technical / Problema con app | Out of scope |
   | Service / Calidad de servicio | Out of scope |
   | Branch / Atención en sucursal | Out of scope |

   Complaints without a subcategory follow their category. The contact-center baseline per reason category (handle time, resolution, escalation, CSAT) is reported as context for PRB-07 and EVL-14 but doesn't enter the choice.
4. **Demo fit.** Whether the three paths and Portuguese come up naturally, and whether a judge can exercise the workflow in a few minutes.

### Revisit

No candidate passed all four gates on the pinned snapshot: only card support passed F1, all four passed F2 and E1, and all four failed E2. The gates are revisited here, before anything is recomputed. Every result was known when this was written, so the revisit follows one principle, stated before what it picks:

> A gate that no candidate can pass on this snapshot, for a reason in the data rather than in any workflow, can't tell the candidates apart. It is set aside, and its results stay in the report as evidence. Every gate that told the candidates apart stays as committed.

E2 is that gate. The dictionary holds no label for account and payment inquiries, and neither of the labels it does hold carries signal on the fields recorded with the event: every held-out ROC AUC interval contains 0.5 (card support 0.493 [0.462, 0.523], dispute intake 0.506 [0.469, 0.543], credit 0.508 [0.498, 0.519]). The one field that tracks `is_fraud` is `fraud_score`, and it is drawn from the label: no legitimate transaction, on any product, scores above 30, while fraudulent ones spread evenly from 0 to 100. `fraud_score` is therefore a noisy copy of `is_fraud`, not a model, and no evaluation uses it as a baseline.

F1 told the candidates apart, so it stays, as do F2 and E1. Its failures don't weigh the same. Credit's is real: about a third of active customers lack a field its eligibility rule reads. Account inquiries' is a fact about the data: account movements never name a merchant, though the workflow could run without one. Dispute intake's falls on `fraud_score` and `claimed_amount`, fields its own rules don't read. The gates therefore show that card support is feasible, not that the others aren't; changing F1 now to readmit them is what the principle rules out (see [Alternatives considered](#alternatives-considered)).

With E2 set aside, card support is the only candidate that passes, so it wins under the rule above. It is also our working hypothesis (see [Context](#context)): the revisit lands where a rule bent towards it would have. The principle, and the other revisits with what each would have chosen, are the guard:

| Revisit | Candidates that pass | Chosen |
|---|---|---|
| Set E2 aside (this revision) | Card support | Card support |
| Also drop F1's rule that a field with no rows fails | Card support; account and payment inquiries | Account and payment inquiries, on evaluation depth (3 of 4 situations covered, against 2 of 4) |
| Also count fields under 90% as material for missing-data cases (EVL-02) instead of F1 failures | All four | Credit information and eligibility, on evaluation depth (4 of 4) |

`make analysis` counts a situation as covered when at least 100 customers back it. That threshold, taken from F2, was set in code after the gates ran; nothing above fixed it. Card support's unsupported-request case sits just under it, at 96 customers.

Setting E2 aside leaves DML-07 without a learned component, so the component moves to the evaluation ADR, with labels we write: a classifier of the customer's request, in Spanish and Portuguese, that routes it to a supported request, an unsupported one, or a human (CTL-01, CTL-03). Its labels come from the workflow policy's list of requests, written before the requests it is tested on, and it is compared with a keyword router on held-out requests; the evaluation ADR fixes the model, the baseline, and the split, and justifies them (DML-10, DML-11). The weakness named under counting labels we write towards E2 stands: the component's case for DML-07 and DML-08 rests on our labels, not on the bank's records.

### Result

On snapshot `b3b8b248f604ef9a`, as of 2026-06-18 06:00 (business date 2026-06-17), from the [selection report](../analysis/selection.md):

| Candidate | F1: fields | F2: state | E1: reference outcomes | E2 (set aside) |
|---|---|---|---|---|
| Account and payment inquiries | fails: `merchant_name` has no rows | passes: 48,477 customers | passes | no label |
| Card support | passes: lowest 94.95% | passes: 32,588 customers | passes | ROC AUC 0.493 [0.462, 0.523] |
| Transaction-dispute intake | fails: `fraud_score` 80.19%, `claimed_amount` 33.01% | passes: 38,598 customers | passes | ROC AUC 0.506 [0.469, 0.543] |
| Credit information and eligibility | fails: `credit_score` 85.01%, `estimated_monthly_income` 79.98% | passes: 86,897 customers | passes | ROC AUC 0.508 [0.498, 0.519] |

**We choose card support.** It is the only candidate that passes the gates, so the judgment's criteria don't run. Its normal path serves the signed-in customer's active credit or debit cards: their status and available credit, declines explained by their response codes, and a block on the customer's confirmation, verified in the sandbox. A charge the customer doesn't recognize goes to review, marked `is_fraud` or not, and hands off to dispute intake with a structured payload (CTL-05), without doing its steps.

## Alternatives considered

**Rank by the agent time and customer pain of each workflow's contacts** (the first draft). It would have been the strongest evidence of need, but it depends on attributing contacts to workflows, which this snapshot can't do.

**Rank by complaint volume.** Complaints are the only demand that can be attributed, but only disputes produce them by nature; card and credit questions rarely become complaints, so the ranking would favor disputes by construction.

**Split the six reasons across workflows with fixed shares.** It would produce a ranking, but from shares we invented, presented as if they were evidence.

**A weighted sum over seven criteria** (demand, cost, pain, feasibility, risk, evaluability, demo fit). Seven weights invite the charge that they were tuned to the answer, and two of the criteria overlap: cost is volume times handle time, so weighting demand and cost counts volume twice.

**Count labels we write ourselves towards E2.** Every candidate would pass, so E2 would stop filtering, and a learned component trained on our own labels makes a weaker case for DML-07 and DML-08 than one trained on the bank's records.

**Build the working hypothesis and justify it afterwards.** Fastest, but PRB-05 asks for a choice justified by reproducible analysis, and an untested hypothesis would carry the whole build.

**At the revisit, also drop F1's rule that a field with no rows fails.** Account and payment inquiries would pass beside card support and win on evaluation depth. The rule was fixed before any gate ran, so that no field could leave the committed lists, and the empty rows are a fact about the data, not an error in measuring it: account products carry only transfers, withdrawals, deposits, and payments, every purchase (debit ones included) sits on a card product, and no account movement names a merchant. Its lead on depth is also thinner than the count: its unsupported-request case, a movement the customer asks about that isn't there, is backed by every account holder by construction.

**At the revisit, also count fields under 90% as material for missing-data cases instead of F1 failures.** All four would pass, and credit would win on evaluation depth. F1 asks whether the normal path can run on the fields its tools read, and for credit it measured that often it can't: 40,803 active customers lack a field the eligibility rule reads, against 86,897 who have both, so about a third of credit requests would go to review on the first turn. Counting those gaps as test material would turn the reason a candidate failed into a reason to choose it.

**At the revisit, leave DML-07 to the LLM judge.** A judge validated against human grading is needed under EVL-10 whatever the learned component is; as the only one, it would measure how we grade, not how the workflow decides.

## Consequences

Positive:
- Anyone can rerun the gates, and the evidence that contacts can't be attributed, with `make analysis` on the pinned snapshot.
- The git history shows the rule, including how each gate is measured and the order of the judgment criteria, before any gate ran.
- The limits of the contact-center data are reported as findings (PRB-03, SCP-07) instead of being hidden behind a ranking.
- The same run produces the human baseline per reason category (PRB-07) and the evidence for PRB-01 to PRB-04.
- That no supplied label carries signal, and that `fraud_score` is drawn from `is_fraud`, is reported as a data limitation (PRB-03, SCP-07) instead of hidden behind a model that learned the leak.
- Card support's normal path runs the whole loop the brief asks for: explain verified facts, act on confirmation, verify the result, and hand off (CTL-02, AI-05, CTL-05).

Negative:
- The choice rests on feasibility and judgment, not on measured demand; the ADR can't claim that customers need the chosen workflow most.
- Our favorite can still win on judgment; the fixed order and the written arguments are the only guard.
- The revisit was written with every gate result in view, and it chose our working hypothesis; its principle, and the other revisits with what each would have chosen, are the only guard.
- No component learns from a label the bank recorded: DML-07 and DML-08 rest on labels we write.
- Requiring data labels can reject a workflow that would work well with labels we write.
- Attributable demand is lopsided: only complaints can be attributed, and only to disputes.
- E2 is indirect for two candidates: the dispute label isn't tied to any dispute, and credit's features and label come from one snapshot with no history.
- F1 measures whether a field is populated, not whether it is right. Card support passed it on `expiration_date` (95.09%), yet about half of all cards, in every status, are past their expiration date, and active ones keep transacting after it.
- The thresholds (99%, 90%, 100 customers, 30 and 60 days, 30 days past due, the 95% interval) and the measurement settings (the feature lists, the held-out fifth, C = 1, 1,000 resamples) are conventions, not derived values.

For the evaluation:
- Two of card support's situations are thin in natural records: in the 30 days before the as-of instant, 96 customers have a decline with a missing `response_code` and 34 have a transaction marked `is_fraud` on an active card (289 and 117 over 90 days, before the held-out fifth is taken). The evaluation ADR sizes the held-out cases against held-out customers, with a longer window and built cases.
- Declines carry only the four codes the rule explains, in equal shares, plus about 5% missing; the rule's branch for an unlisted code never occurs, so its cases are built. Every card transaction sits on an active card, so cases with a blocked or closed card and recent activity are built too.
- Core fields miss about 5% of values at random, independently of each other: material for missing-data cases (EVL-02), reported as injected rather than realistic (SCP-07).
- An active card past its expiration date is a conflict the tools surface, not a fact they report or resolve; the policy says what the agent does with it, and the held-out cases include it.
- `is_fraud` is flat, so no expected outcome treats it as the truth of a customer's claim; it stands only for the bank's own flag.
