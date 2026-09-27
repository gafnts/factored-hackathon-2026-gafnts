# ADR-0003: Choose the workflow from evidence

## Status

Proposed (2026-09-27). This revision fixes the rule before any gate has been computed for any workflow; the evidence and the choice are added when the ADR is accepted.

The table-level [data quality profile](../analysis/profiling.md) ran before this revision was committed, and it changed the rule. The first draft ranked the workflows by the agent time and customer pain of their contacts, which the profile showed can't be measured (see Context). Its table-wide null rates also bear on gate F1, which keeps the threshold it was drafted with.

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

The business date is the last day for which every daily table can be expected to hold at least 99% of its rows, given how late rows arrived over the rest of the history. Each processing day runs past midnight, to a fixed cutoff the next morning, so "the 30 days before the business date" counts events by their own timestamp, never by `process_date`.

### Gates

A candidate must pass all four.

| Gate | Passes when |
|---|---|
| F1: fields | The fields its core tools read (table below) are at least 90% populated in the rows those tools would read |
| F2: state | At least 100 customers are, at the business date, in the state its normal path needs (table below) |
| E1: reference outcomes | Its expected outcomes can be written as deterministic rules over the frozen state; the ADR sketches three such rules and the fields they read |
| E2: learned component | A label that comes from the supplied data, never one we write, shows signal on held-out customers (DML-07 to DML-09): a logistic regression on fields recorded with the event reaches a held-out ROC AUC whose 95% bootstrap interval lies above 0.5, with training and held-out customers kept apart |

Fields and states, taken from the data dictionary before looking at the data:

| Candidate | Core fields | Normal-path state |
|---|---|---|
| Account and payment inquiries | `products`: `product_type`, `product_status`, `current_balance`, `currency`; `transactions`: `transaction_date`, `amount`, `transaction_type`, `transaction_status`, `merchant_name`, `channel` | An active checking or savings account with a transaction in the 30 days before the business date |
| Card support | `products`: `product_type`, `product_status`, `credit_limit`, `current_balance`, `expiration_date`; `transactions`: `transaction_status`, `response_code`, `is_fraud`, `merchant_name`, `channel`, `transaction_country` | An active credit or debit card with a transaction in the 30 days before the business date |
| Transaction-dispute intake | `transactions`: `transaction_date`, `amount`, `currency`, `transaction_status`, `merchant_name`, `is_fraud`, `fraud_score`; `complaints`: `case_type`, `claimed_amount`, `status` | An approved purchase in the 60 days before the business date |
| Credit information and eligibility | `customers`: `credit_score`, `estimated_monthly_income`, `segment`, `customer_status`; `products`: `product_type`, `credit_limit`, `interest_rate`, `days_past_due` | An active customer with `credit_score` and `estimated_monthly_income` populated |

Labels for E2, also from the dictionary. The features never include `fraud_score` or `response_code`, which may already encode the answer; `fraud_score` is kept as the bank's existing model, the baseline a later evaluation compares against.

| Candidate | Label | What the learned component would do |
|---|---|---|
| Account and payment inquiries | None in the dictionary | Nothing, so the candidate fails E2 |
| Card support | `is_fraud` on card transactions | Score a transaction as suspicious, to offer a card block or hand off |
| Transaction-dispute intake | `is_fraud` on the disputed transaction | Triage a dispute as likely fraud or a merchant disagreement |
| Credit information and eligibility | `days_past_due` of 30 or more on credit products | Estimate repayment risk, kept apart from eligibility policy (CRD-01) |

If exactly one candidate passes, it wins. If none does, the gates are revisited in writing before anything else.

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

## Alternatives considered

**Rank by the agent time and customer pain of each workflow's contacts** (the first draft). It would have been the strongest evidence of need, but it depends on attributing contacts to workflows, which this snapshot can't do.

**Rank by complaint volume.** Complaints are the only demand that can be attributed, but only disputes produce them by nature; card and credit questions rarely become complaints, so the ranking would favor disputes by construction.

**Split the six reasons across workflows with fixed shares.** It would produce a ranking, but from shares we invented, presented as if they were evidence.

**A weighted sum over seven criteria** (demand, cost, pain, feasibility, risk, evaluability, demo fit). Seven weights invite the charge that they were tuned to the answer, and two of the criteria overlap: cost is volume times handle time, so weighting demand and cost counts volume twice.

**Count labels we write ourselves towards E2.** Every candidate would pass, so E2 would stop filtering, and a learned component trained on our own labels makes a weaker case for DML-07 and DML-08 than one trained on the bank's records.

**Build the working hypothesis and justify it afterwards.** Fastest, but PRB-05 asks for a choice justified by reproducible analysis, and an untested hypothesis would carry the whole build.

## Consequences

Positive:
- Anyone can rerun the gates, and the evidence that contacts can't be attributed, with `make analysis` on the pinned snapshot.
- The git history shows the rule, including the order of the judgment criteria, before any gate ran.
- The limits of the contact-center data are reported as findings (PRB-03, SCP-07) instead of being hidden behind a ranking.
- The same run produces the human baseline per reason category (PRB-07) and the evidence for PRB-01 to PRB-04.

Negative:
- The choice rests on feasibility and judgment, not on measured demand; the ADR can't claim that customers need the chosen workflow most.
- Our favorite can still win on judgment; the fixed order and the written arguments are the only guard.
- Requiring data labels can reject a workflow that would work well with labels we write.
- Attributable demand is lopsided: only complaints can be attributed, and only to disputes.
- The thresholds (99%, 90%, 100 customers, 30 and 60 days, 30 days past due, the 95% interval) are conventions, not derived values.
