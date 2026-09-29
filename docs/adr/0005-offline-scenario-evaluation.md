# ADR-0005: Offline scenario evaluation against an independent policy oracle

## Status

Proposed (2026-09-27).

Some decisions are still open. Each is marked **Open** where it arises and listed under [Open decisions](#open-decisions) with the option we lean towards, which the rest of this record assumes; we settle them before accepting it.

## Context

The organizers grade demonstrated behavior and honesty about it: results on a held-out workload against a baseline (EVL-01), cases with incorrect or missing data, expired sessions, unauthorized access, injection, tool failures, and mixed languages (EVL-02 to EVL-07), metrics M-01 to M-05 with sample sizes (EVL-11), per language and segment (EVL-12), failures included (EVL-09), and a learned component against a baseline (DML-07). Six forces shape how:

- **The data holds no ground truth for the agent.** No supplied label carries signal, contacts can't be tied to a workflow, and the transcripts are templated ([ADR-0003](0003-choose-workflow-from-evidence.md)). Expected outcomes therefore come from the [card support policy](../policy/card-support.md) applied to the frozen state, never from historical outcomes.
- **The request mix is unknown.** Nothing in the snapshot says how often customers ask each question, so a rate over cases describes the cases we wrote, not a bank's traffic, and must be reported that way (EVL-13). Only the volume is known: the [traffic analysis](../analysis/traffic.md) counts the bank's contacts per day and hour, finds no daily cycle, and projects the agent's load from them under assumptions (turns per conversation, model calls per turn, tokens per call) that this evaluation can measure.
- **Some situations are thin or absent.** Among development customers, a decline with no listed code backs 75, 231, and 972 customers in 30, 90, and 365 days, and a transaction marked `is_fraud` on an active card backs 27, 87, and 360. Unlisted codes, and blocked or closed cards with recent activity, never occur ([card support analysis](../analysis/card-support.md)).
- **A split already exists.** ADR-0003 holds out customers whose `customer_id` has an MD5 divisible by 5: 29,825 of the 150,000 registered by the as-of instant. The analysis and the policy read the other 120,175 only, and the demo personas will too.
- **The system records itself.** [ADR-0004](0004-agent-architecture-on-agentcore.md) writes an execution record for every model call, tool call, decision, interrupt, and resume, keeps writes in a sandbox per sign-in, and lets an evaluation harness add fixtures and faults there. Access and actions are enforced outside the model, so they can be graded without it.
- **Model calls cost money and are rate limited.** The providers' limits, and Gemini 3.1 Pro's daily cap, bound how often the held-out workload can run.

## Decision

Evaluate offline, on scenarios: authored conversations played against the snapshot's customer states through the deployed system, graded first by code against an oracle that applies the policy to the frozen state independently of the tools, and by a validated judge only for language and wording.

### What a case is

One customer from one split, one scripted conversation from one authored request family in one language, optional fixtures and faults, and the outcome the oracle expects:

- **Script:** the customer's turns, which are messages, presses of the confirm control (confirm or cancel), and harness actions (wait past a time limit, sign out, send another customer's thread ID).
- **Fixtures and faults:** records the snapshot lacks, added to the case's own sandbox (a transaction with an unlisted code, a merchant name that carries an injection), and fault plans (a tool that fails N times). Only the harness's role can write them, and tools honor them only in the sign-in they were written for (ADR-0004).
- **Expected outcome, per turn:** the labels in order; the outcome class (answer, clarify, abstain, decline, block, or hand off); the tool calls required and forbidden; the facts the reply must state, formatted as the system formats them; the content it must not hold; the handoff's reason code, queue, priority, trigger, rules, and verified facts; the sandbox's end state; and the rule IDs the case exercises.

### Coverage and size

About 600 held-out cases, 300 per language (**Open**, decision 1). Every group has cases in both languages, and every policy rule is exercised by at least one case.

| Group | Covers | Requirements | Cases per language | Source |
|---|---|---|---|---|
| Reads | Status, available credit, recent transactions, a decline explained | SCP-03, AI-03 | 70 | Natural |
| Block | Each reason, confirmed with the control, verified | SCP-03, CTL-02, AI-05 | 30 | Natural |
| Clarify or decline | Several cards, no match, last-four collisions, the question limit, unsupported requests, other products, small talk | SCP-04, AI-02, CTL-01 | 40 | Natural; collisions within a type are built |
| Handoffs | Unrecognized charges (found or not, marked or not; block confirmed, cancelled, or lapsed), asking for a person, a complaint, an unblock, a customer who isn't active | SCP-05, CTL-03, CTL-05 | 40 | Natural |
| Incorrect or missing data | No limit, over the limit, no code, an unlisted code, past expiration, before opening, code `54` before the recorded expiration, no merchant | EVL-02 | 35 | Natural; unlisted codes, and blocked or closed cards with recent activity, are built |
| Expired sessions | A message after the token expires, a confirmation after its time limit or after sign-out, a stale control | EVL-03 | 10 | Harness |
| Unauthorized access | Another customer's card or ID in a message, another customer's thread or runtime session ID, a tool called directly with another customer's ID, the attribute rewrite that spike S3 found | EVL-04, SEC-04, SEC-05 | 20 | Harness |
| Prompt injection | Instructions in messages, and in a merchant name | EVL-05 | 20 | Authored; merchant names are built |
| Tool failures | A read that recovers within its retries, one that doesn't, a block that doesn't verify, a denial | EVL-06, OPS-04 to OPS-06 | 15 | Fault plans |
| Multilingual ambiguity | Spanish and Portuguese mixed, a switch mid-conversation, a third language, one-word replies | EVL-07, SCP-06 | 10 | Authored |
| Confirmation | A typed yes, a cancel, a lapse by a new request, a confirm sent again after a block, a change of card | CTL-02 | 10 | Harness |

"Natural" means the customer's own records supply the situation; "built" means a fixture adds it, and the case is labeled built in every report; "harness" means the harness produces it (tokens, IDs, timing); "authored" means the message carries it.

**Sized against the held-out fifth.** The held-out customers stay unread until this plan is frozen, and the generator reports the real counts when it draws cases. By proportion (29,825 against 120,175 development customers) the thin situations should hold about a quarter of the development counts: about 57 customers with a decline that has no listed code and about 22 with an `is_fraud` mark on an active card within the 90 days the tools read. Cases use that 90-day window throughout. A situation short of its target is topped up with built cases, and the report gives the natural and built counts separately.

**Customers** are drawn within each group in proportion to held-out card holders by country (Mexico's cards are all in USD, and its number format differs from Colombia's and Argentina's), with at least 30 cases per segment in each language. Student customers are about 4.9% of development customers with an active card, so the floor oversamples them about twice; overall rates are reported unweighted, since the mix is ours either way. The held-out distribution is therefore realistic in state, the held-out customers' own records, but not in demand, which the data can't give (DML-10).

**Precision.** With 300 cases, a rate near 90% has a 95% interval about 3.5 points wide on either side; with 30 cases in a segment, about 11. So segment comparisons can flag only large gaps, and the report says so. For M-04, zero unsafe outcomes in 600 cases would bound the rate below about 0.5% at 95% (the rule of three); repeated runs of the same cases aren't independent draws, so the bound counts cases, not runs.

**Repeats.** Each held-out case runs three times per configuration (EVL-08), so the report can show how often a case's outcome changes between runs.

### The split

A case is held out only if all three groupings put it there (DML-09):

1. **By customer.** Held out when the MD5 of `customer_id` is divisible by 5 (ADR-0003's rule). Development cases, prompts, prompt examples, router training data, and demo personas use development customers only.
2. **By authored request family.** A family is one authored request with its paraphrases, about five per language, in Spanish and Portuguese together; injection attempts and mixed-language messages are families too. Each family is assigned whole to one side, so a paraphrase can't leak a held-out request into training or tuning. Lean: 12 families per label, a third of each label's held out (**Open**, decision 2).
3. **By time.** Customer grouping already isolates the state, so time governs the order in which things are seen (**Open**, decision 3). Cases read events up to the as-of instant only (ADR-0004's event cutoff). The held-out set is generated once, and its manifest's hash is committed before the first run that reports it. No held-out case is edited after a run: a problem it reveals becomes a new development case, and a changed held-out set is a new version, with earlier results reported against the old one.

Tests guard the split. No development artifact (cases, prompts, router data, personas) may hold a held-out customer ID or a held-out family's text, and the split functions are shared code with their own tests.

### The development regression set

About 50 cases from development customers and development families: the three paths in both languages, and one case for each main failure mode (a confirmation, an access attempt, an injection, a tool failure, missing data). It runs on every change to the graph, prompts, tools, or policy, is logged like any run, and never appears as a reported result. Its deterministic part, with scripted model outputs and no provider calls, runs in CI on every push and checks the control logic: confirmation, masking, thread scoping, handoff validation, and retries. The held-out workload runs only for reported results, each run with its manifest.

### The oracle

- **Written from the policy's text, independently of the tools.** SQL over the pipeline's bronze tables, the typed copy of the snapshot ([ADR-0006](0006-batch-medallion-pipeline.md)), rather than the gold tables the tools read, so that a transformation bug shows up as a disagreement instead of agreeing with itself. It lives in the evaluation package and shares no code with the tools.
- **Computes each case's expected outcome** from the customer's state, the script's parameters (which card the customer names, and how), and the case's fixtures.
- **Disagreements are triaged in writing.** When the system and the oracle differ, the log records whether the oracle, the system, or the policy's wording was wrong. A wording fault becomes a policy change, which raises the version once the policy is accepted. The log is published with the report.

### Running a case

- **Identity:** the harness creates a Cognito test user for each case customer before the run, with `custom:customer_id` set by an admin and membership in an evaluation group, and deletes them afterwards (**Open**, decision 8). Their credentials never leave the machine running the harness.
- **End to end:** each case signs in afresh, so its sandbox starts clean; writes its fixtures and fault plans under that sign-in; and plays the script against the deployed Runtime over AG-UI, sending controls as resume entries (**Open**, decision 7). Waits are real, run in parallel batches: an expired-token case waits out the 15-minute token.
- **Direct tool calls:** the unauthorized-access group also calls the Gateway's tools directly with one customer's token and another's `customer_id`, as a fully compromised agent would; Cedar must deny every call.
- **Records:** execution records carry `source=evaluation` and the case ID. Parallelism is set from the providers' limits.

### Grading

**Deterministic first,** from the execution record and the sandbox:

- the labels and their order, against the case's;
- the outcome class of each turn;
- the tool calls: required ones made, forbidden ones absent (no block without a used confirmation, no call for another customer that succeeds);
- the facts: each expected fact appears as formatted, and no other figure does;
- the handoff: it validates against the schema, and its reason code, queue, priority, trigger, rules, and verified facts match the oracle's;
- the sandbox: the card's end state, and at most one block per confirmation;
- forbidden content: a full card number, another customer's data, an `is_fraud` or `fraud_score` value, a customer status the policy withholds, a promised outcome.

**A judge only for language and wording:** whether the reply is in the expected language with the policy's form of address ("usted", "você"; POL-50); whether it says in words what the policy requires (a person will follow up, with the reference and no promised outcome; the card wasn't blocked after a lapse; both conflicting facts, with neither chosen; a code's meaning and nothing more; no fraud verdict or refund); and whether it is clear. The rubric is in the repository as typed questions (a choice, a yes or no, a score), each citing its rule.

**Validated before use** (EVL-10). We grade a stratified sample of replies by hand, without seeing the judge's answers (**Open**, decision 6; lean: 30 in Portuguese and 30 in Spanish). The report gives agreement and Cohen's kappa per question, with intervals. A question is graded by the judge only if its agreement reaches 90%, a bar fixed here, before any grading; otherwise we grade those replies by hand or drop the question, and the report says which. Judgments below a confidence threshold are graded by hand.

**Candidates** (**Open**, decision 5): an LLM judge from a provider other than the agent's under test, so it doesn't grade its own model's writing, and Jev, whose typed answers, calibrated probabilities, and low variance fit this rubric (spike S5 in ADR-0004). Jev is weak on numbers and dates, which the deterministic grader covers. Both are validated on the same sample, the better one is used per question, and both results are reported.

### Baselines

- **The system against a deterministic baseline** (EVL-01), on the same held-out workload: the same graph, tools, confirmation, and handoff builder, with a keyword router, pattern-based extraction, and templated replies, so no model runs anywhere (**Open**, decision 4). The comparison shows what the models add, and at what cost and risk (DSN-03).
- **The router** (DML-07, DML-11, DML-12), the learned component ADR-0003 moved here. Four candidates on held-out families, per language: the keyword router as the baseline, an LLM classifier through structured output, multilingual embeddings with logistic regression trained on development families, and Jev. Each returns the requests present and the separate yes or no on whether there is one. Reported: macro F1 and recall per label on the first request (POL-05's order), multi-request detection, the no-request gate's accuracy, calibration where a candidate gives probabilities, latency, and cost per call, with a confusion matrix and the errors read by hand per language. The router in the system is chosen by cross-validation over development families, grouped by family, before the held-out run (**Open**, decision 9).
- **Labels** (DML-08, EVL-08) come from the policy's request list. Each message carries its family's label; we relabel a sample of 100 messages by hand, blind to that label, the agreement is reported, and a disagreement is settled by the policy's text, the message dropped if the text can't settle it. Seeds are written by us and paraphrases generated by a model and reviewed, all labeled team-generated (SEC-02).
- **The human baseline** (PRB-07): the contact center's handle time, first-contact resolution, escalation, and CSAT per reason category, from the [selection report](../analysis/selection.md#contact-center-baseline). It is context for the ROI, not a case-by-case comparison, since contacts can't be tied to requests; the ROI is labeled a projection (EVL-13, EVL-14).

### Reporting

The metrics follow [their definitions](../hackathon-requirements.md#metric-definitions), overall, per language, and per segment, each with its sample size, a 95% Wilson interval, and its spread over the three runs (EVL-08, EVL-11, EVL-12):

- **M-01:** eligible cases resolved correctly without a person, over all cases in scope (every case is), with the share of cases where automation was attempted. A case is eligible when the oracle's outcome needs no person: an answer (after clarifying, if needed), a decline or an abstention with its reason, or a verified block, with no handoff required or accepted. M-01 is also given by outcome class, so answers aren't mixed with declines.
- **M-02:** cases that end without a transfer, never reported alone.
- **M-03:** of the cases the oracle hands off, the share transferred with the right reason, queue, priority, and a payload that validates and holds the expected facts; missed and unnecessary transfers are counted separately.
- **M-04:** counts with their denominators, by kind: a disclosure (another customer's data, a full card number, an internal flag, a withheld status), an action (a block without a confirmation, on the wrong card, or twice on one), and a materially incorrect outcome (a wrong fact stated as verified, a block reported but not verified, a required handoff missing). Zero is reported with its rule-of-three bound.
- **M-05:** end-to-end latency per turn and per case (p50, p95), from the harness sending to the last event; cost per attempted case; and cost per successful automated resolution, "not defined" when there is none. Cost counts model tokens at each provider's list price on the run date, plus AWS charges estimated from the Runtime's, Lambda's, and DynamoDB's prices for the case's usage, with every assumption listed. The workload M-05 states is the run's own: cases, turns, repeats, and parallelism, never the bank's traffic. The report also gives the turns, model calls, and tokens per case it measured, which replace the traffic analysis's assumed values when its projection is next computed, and the projection stays labeled as one (EVL-13).

Results are also given by group, by rule, and by country, so a failure points at a rule, and with and without cards flagged as updated after the as-of instant (ADR-0004). Every failed case is counted and classified (EVL-09), and a sample is shown with its execution record, masked. A gap between languages or segments wider than the intervals explain is investigated and written up (EVL-12). The report states the case mix, the label quality, and the model and prompt versions, and it calls every number an offline measurement (EVL-13). It publishes aggregates only, with counts under 10 suppressed (SEC-03). Per-case results stay in an evaluation bucket in the project's account for 90 days.

**Model selection** (DML-12). The model grid (the three models of spike S2 in ADR-0004) runs on the development set, and the configuration for the held-out run is chosen there, by fewest unsafe outcomes, then M-01, then cost and latency (**Open**, decision 10). The held-out workload runs the chosen configuration and the baseline; other configurations may run on it as secondary results, never used to choose.

### The run manifest

Every run writes a manifest: the run ID and wall-clock times; the git SHA and whether the tree was clean; the snapshot ID and pipeline version; the policy and handoff schema versions; a hash of each prompt; per node, the model requested and the `model_name` returned, the provider, and the reasoning and sampling settings; the router and judge used, with the rubric's version; the case set's version and hash, and the oracle's version; hashes of the fixtures and fault plans; the deployed stack's version; parallelism, repeats, and seeds; token and cost totals; and hashes of the results. The manifest and the aggregate report are committed under `docs/evaluation/`; the per-case results they hash stay in the evaluation bucket. That is the experiment tracking (DML-12); LangSmith may mirror runs but is never needed to reproduce one (OPS-07).

### Policy impact on the frozen state

The oracle also counts, over development customers, how the policy would treat each card, per request: answered, clarified first, abstained, declined, or handed off (required or offered), with the rule that decides it, in cards and in customers rather than cases. The request mix is unknown, so a count of cases would measure how we wrote them; a count of cards says how often a rule fires when a request is about that card. It applies the rules in the policy's order (identity, then the customer's status, then the request), so it doesn't simply add up the analysis's separate counts: for example, a card over its limit that belongs to a suspended customer is handed off for its status, not answered for its limit. The table has one row per request and deciding rule, with the outcome and the counts of cards and customers.

It is published by `make analysis`, under the same rules as the other reports, and feeds the limitations (SCP-07), the operational constraints (PRB-04), and the ROI.

### Open decisions

We settle these before accepting this record. Each names the option we lean towards, which the rest of the record assumes, and any alternative still in play.

1. **Size and mix.** Lean: about 600 held-out cases, 300 per language, in the groups above, with at least 30 per segment per language, each run three times.
2. **Request families.** Lean: 12 per label, a third of each held out, about five paraphrases per language.
3. **What "by time" means.** Lean: the event cutoff and the order of freezing, since customer grouping already isolates the state.
4. **The EVL-01 baseline.** Lean: the deterministic system (keyword router, pattern-based extraction, templated replies), so no model runs. Alternative: our system with only the keyword router swapped in, which isolates the router but compares two systems that are nearly the same.
5. **The judge.** Lean: validate an LLM judge and Jev side by side and use the better per question, with the 90% bar.
6. **Hand grading.** Lean: 30 Portuguese and 30 Spanish replies for the judge, and 100 messages for label quality.
7. **Where held-out runs execute.** Lean: end to end on the deployed stack, so latency is real and access cases meet the real authorizers and Cedar. Alternative: the graph in-process against the deployed tools, faster but blind to the Runtime.
8. **Test identities.** Lean: created per run and deleted after it. Alternative: kept between runs, which is faster to rerun but leaves held-out customer IDs in Cognito.
9. **The router's selection.** Lean: four candidates, chosen by cross-validation over development families before the held-out run.
10. **The model configuration.** Lean: chosen on the development set; the held-out workload runs it and the baseline, and other configurations only as secondary results.

## Alternatives considered

**Grade against historical outcomes.** Contacts can't be tied to requests, and their resolutions can't be tied to what the agent should have done (ADR-0003).

**Use the tools as the oracle.** The evaluation would check the code against itself: a bug in a tool or in the gold tables would also be in the expected outcome.

**An LLM judge for everything.** Facts, actions, and access can be graded exactly from the execution record, and a judge would add variance there; EVL-10's validation is needed for whatever it judges, so it judges only what code can't.

**A random split of cases.** Paraphrases of one request, or one customer's cases, on both sides would inflate the router's and the system's scores (DML-09).

**Built cases only.** They would cover every branch evenly, but lose the real state's gaps and conflicts, which are what the policy most needs to meet. Natural state comes first, and built cases only fill what it lacks.

**A harness from LangSmith or AgentCore Evaluations.** Either could host the runs, but the grading reads our own execution records and must run without either (OPS-07). LangSmith may mirror runs, and AgentCore's evaluators could later serve as a monitoring signal (OPS-03).

**Count policy impact in cases.** It would measure our authoring, not the policy.

## Consequences

Positive:
- Expected outcomes don't depend on the code under test: the oracle reads another layer, through other code.
- Three groupings, tested, keep development work away from held-out results.
- Access, actions, and facts are graded exactly; the judge covers language and wording only, and its agreement with a person is published.
- Failures, small samples, built cases, and the unknown request mix are reported as such, rather than hidden in an overall rate.
- Any run can be traced to its code, data, policy, prompts, and models through its manifest, and repeated.
- The policy's effect on the frozen state is measured in cards, which says how often each rule fires without inventing demand.

Negative:
- Every request is authored by us, not written by real customers; no real request exists in the data, and every transcript in it is Spanish, so Portuguese rests on our own messages (SCP-07).
- The oracle's independence is of code and data layer, not of people: the same team wrote both from the same policy.
- About 600 cases resolve language comparisons to a few points and segment comparisons only to large gaps.
- The judge's validation rests on one grader.
- Built cases are ours, and the report can only label them.
- End-to-end runs are slow (real waits, cold starts) and cost money, so the held-out workload can't be rerun freely.
- No rate here predicts production traffic, whose mix is unknown.
