# Product brief

Faro is the card support agent we are building for LATAM Bank. This brief says what problem it takes on, who it serves, what it does and refuses to do, what sets it apart, and the outcomes we intend (PRB-06). The details are decided elsewhere, in the policy and the ADRs; this brief links to them rather than restating them.

> [!IMPORTANT]
> **A synthetic bank (SEC-02).** LATAM Bank is the regional bank the organizers' dataset simulates, in Mexico, Colombia, and Argentina; every customer, card, and transaction in it is synthetic. The outcomes below are intentions, each with the measure it will be judged by; none is a measured production result (EVL-13).

## Contents

- [In one sentence](#in-one-sentence)
- [The problem](#the-problem)
- [Who it's for](#who-its-for)
- [What Faro does](#what-faro-does)
- [What Faro won't do](#what-faro-wont-do)
- [What sets it apart](#what-sets-it-apart)
- [Intended outcomes](#intended-outcomes)
- [Out of scope](#out-of-scope)
- [Where the decisions live](#where-the-decisions-live)

---

## In one sentence

> **Faro is LATAM Bank's card support agent, in Spanish and Portuguese. It explains what the records say, blocks a card only when its holder confirms, and hands off to a person with a structured case file.**

The name carries the idea. In Spanish, *faro* is a lighthouse; in Portuguese, *ter faro* is to have a nose for things. Guidance in one language, judgment in the other. The [identity guide](identity.md) says how Faro sounds and looks.

---

## The problem

A card is declined at the till, goes missing, or shows a charge its holder didn't make. In that moment the customer wants two things: to know why, and to stop the damage. The bank wants what sounds like the opposite: to act only on the right card, for the right person, when that person asks. A person on the phone does both, after a wait. An agent that acts on whatever the conversation says is fast and unsafe. Faro is built to be both quick and safe, in the customer's language.

What the data shows about that moment:

- **Declines are routine.** 62,242 card transactions (5.02%) are declined over the snapshot, each with a response code the bank can explain ([card support analysis](../analysis/card-support.md#3-declines)).
- **Unrecognized charges end up as complaints.** In the 12 months before the as-of instant, 4,175 complaints (18.57%) were about a charge the customer didn't recognize ([selection report](../analysis/selection.md#attributable-demand)). They belong to dispute intake, which is where Faro hands them.
- **Customers hold several cards.** 13,420 of the 65,796 development customers with an active card hold two or more active credit cards, so "block my card" often needs "which one?" first (POL-14).
- **The records are imperfect.** 47.69% of active cards are past their expiration date and still transact, and about 5% of each core field is missing at random. Grounded answers say what the record says, conflicts and gaps included (POL-30 to POL-32).
- **A contact with a person takes minutes.** It takes 5:22 on average, after a 2:00 wait, across every contact reason ([traffic analysis](../analysis/traffic.md#7-handle-and-wait-times)). That's the human baseline for the ROI, not a case-by-case comparison ([ADR-0005](../adr/0005-offline-scenario-evaluation.md#baselines)).

And what it can't show: **how many contacts are about cards.** The snapshot's contacts can't be tied to a workflow: they carry six coarse reasons and templated transcripts ([ADR-0003](../adr/0003-choose-workflow-from-evidence.md)). We chose card support because it's the only workflow the data supports end to end, not because it's the largest.

---

## Who it's for

Three kinds of people use Faro. Only the cardholder talks to Faro, and the AI team reads the evaluation report in the repository rather than on the site ([ADR-0007](../adr/0007-role-gated-web-app.md#status)).

| Who | Their moment | What they get | Where |
|---|---|---|---|
| **The cardholder** | Their card was declined, is missing, or shows a charge they didn't make | An answer from their own records, in their language; a block they confirmed and Faro verified; a reference when a person takes over | `/chat` |
| **The human agent** | A case lands in their queue | A case file: the request, each verified fact next to the tool call that read it, the actions with their verified outcomes, the customer's own words kept apart, and the open questions. No transcript to read back | `/agent` |
| **The AI team** | Deciding whether Faro is safe to keep running | The evaluation report, failures and denominators included, labeled as an offline measurement | `docs/evaluation/`, linked from the README |

**The cardholder** is a LATAM Bank customer in Mexico, Colombia, or Argentina who holds a credit or debit card and has signed in to the bank's chat. Spanish is the bank's language, and Portuguese is the customer's choice in the session ([policy](../policy/card-support.md#language)). No customer in the data writes Portuguese: every transcript is in Spanish. So our Portuguese rests on messages we wrote, and results are reported per language to show whether it holds up (SCP-07, EVL-12).

**The human agent** works in dispute intake or customer service, and takes what Faro shouldn't do: disputes, unblocks, replacements, and anything a record can't settle.

---

## What Faro does

The brief asks for a system that understands, decides, acts, verifies, and escalates (`SL 11`). Faro recognizes [eight kinds of request](../policy/card-support.md#requests), all about cards, and takes one action: a block, written to a sandbox over the frozen bank. Every request ends on one of the brief's three paths:

| Path | The customer says | Faro |
|---|---|---|
| **No. 1 Resolve** (SCP-03) | *¿Por qué me rechazaron la tarjeta ayer?* | Reads the card's transactions, finds yesterday's declined purchase, and gives its date, merchant, amount, and the meaning of its code: `51`, insufficient funds. It infers no cause and gives no advice (POL-02, POL-27, POL-29) |
| **No. 2 Ask or decline** (SCP-04) | *Quiero bloquear mi tarjeta*, from a customer with two active credit cards | Asks which, naming each by type and last four digits, then asks for a reason, then shows the confirm control (POL-14, POL-35, POL-36). *Quero aumentar meu limite* is declined with the reason, and a person is offered (POL-42) |
| **No. 3 Hand off** (SCP-05) | *Não reconheço uma compra no meu cartão* | Finds the charge and offers to block the card with the confirm control. Once the customer confirms, the tool reads the card back to verify the block, and Faro files the case to dispute intake and gives its reference (POL-37, POL-39, POL-45) |

---

## What Faro won't do

Knowing when not to act is half the product (CTL-03):

- **Act on typed text.** A block happens only through the confirm control, which names the card and the reason. A *sí* or *sim* typed in the chat never confirms one (POL-36).
- **Serve anyone but the signed-in customer.** A card number, customer ID, or name typed in the chat never changes whose cards Faro serves (POL-07, POL-08).
- **Undo what lowers risk.** Unblocking restores spending power and needs stronger proof of identity than a chat session gives, so it goes to a person (POL-41).
- **Judge a charge.** Faro doesn't open disputes, promise refunds, or say whether a charge is fraud (POL-39). The bank's `is_fraud` flag is never shown and decides nothing (POL-40).
- **Guess.** A missing field is reported as not recorded, and conflicting records are stated side by side, never reconciled (POL-30, POL-32).
- **Promise.** The reply to a handoff says a person will follow up and gives a reference; it promises no outcome or time (POL-45).
- **Move money.** Nothing Faro does moves money or changes the bank's records; its one write lands in the session's sandbox (POL-33, SEC-07).

---

## What sets it apart

1. **A lighthouse doesn't steer the ship.** Faro shows the customer what the records say and proposes the one thing it can do. The customer's button decides; the model never confirms anything on the customer's behalf.
2. **Judgment in code, not in the prompt.** The model classifies, extracts, and writes. Code decides each step, and the tools and Cedar decide every access and action, so a fully compromised model still can't read another customer's card or block one unconfirmed ([ADR-0004](../adr/0004-agent-architecture-on-agentcore.md)). The evaluation states this as a hypothesis before it runs: unauthorized disclosures and actions stay at zero in every model configuration, and one counterexample refutes it ([ADR-0005](../adr/0005-offline-scenario-evaluation.md#reporting)).
3. **Done means verified.** After a block, the tool reads the card back. Faro says the card is blocked only when that read shows it, and hands the case to a person when it doesn't (POL-37, AI-05).
4. **A handoff is a case file.** Each fact sits next to the tool call that read it, and the customer's words are kept apart from verified facts. The case is urgent when the customer reported a card lost or stolen, or a charge they don't recognize, and that card isn't verified blocked (POL-46, POL-47). Whoever picks it up doesn't start over.
5. **Graded by an oracle that shares no code with it.** Expected outcomes come from the policy applied to the frozen bank, in SQL written apart from the tools, so a bug in Faro's data shows up as a disagreement instead of agreeing with itself ([ADR-0005](../adr/0005-offline-scenario-evaluation.md#the-oracle)).

---

## Intended outcomes

The intended customer is the cardholder above; these are the outcomes we intend for them and for the bank (PRB-06). The right column is how we will know whether the prototype meets each one: offline, on held-out cases, as [ADR-0005](../adr/0005-offline-scenario-evaluation.md) defines the metrics.

| For | We intend | Measured by |
|---|---|---|
| The cardholder | An answer from their own records, in their language, without waiting for a person | M-01, safe automated resolution, per language (EVL-12) |
| The cardholder | Exposure stopped when they ask: a block in the same conversation, verified | M-01 on blocks; M-04's unsafe actions |
| The cardholder | Not having to repeat themselves when a person takes over | M-03: the right queue and priority, and a payload that holds the expected facts |
| The bank | No unsafe outcome, as the condition for everything else | M-04, as counts with denominators and a rule-of-three bound |
| The bank | People's time spent on disputes and judgment calls, not lookups | M-01, with M-03's missed and unnecessary transfers |
| The bank | A resolved case that costs less than a contact handled by a person | M-05 and the cost-per-resolution ROI, labeled a projection (EVL-14) |

What we don't claim: that cards drive most of the bank's contacts, which the data can't say; any saving as measured in production; or that Portuguese works as well as Spanish before the per-language results show it.

---

## Out of scope

- **Other workflows.** Faro hands a disputed charge to dispute intake with a payload and performs none of that workflow's steps (SCP-01, [ADR-0003](../adr/0003-choose-workflow-from-evidence.md)).
- **A person joining the chat.** Handoffs are asynchronous: a case in a queue, not a live transfer ([ADR-0007](../adr/0007-role-gated-web-app.md#in-a-bank-ops-11)).
- **The bank's real systems.** The tools read a frozen snapshot of the bank and write to a sandbox. What they stand in for, and what replacing them would take, is in [ADR-0004](../adr/0004-agent-architecture-on-agentcore.md#the-tools-as-the-seam-to-the-banks-systems).

---

## Where the decisions live

| Question | Where |
|---|---|
| Why card support | [ADR-0003](../adr/0003-choose-workflow-from-evidence.md) and the [selection report](../analysis/selection.md) |
| What Faro answers, does, and refuses | The [card support policy](../policy/card-support.md) |
| What runs where, and what enforces each rule | [ADR-0004](../adr/0004-agent-architecture-on-agentcore.md) |
| How we know it works | [ADR-0005](../adr/0005-offline-scenario-evaluation.md) |
| How the data reaches the tools | [ADR-0006](../adr/0006-batch-medallion-pipeline.md) |
| The web app and the human agent's console | [ADR-0007](../adr/0007-role-gated-web-app.md) |
| How Faro sounds and looks | The [identity guide](identity.md) |
