# Architecture

Faro on one page: what runs where, how a turn flows, what the graph decides, where each rule is enforced, how the data reaches the tools, and how we measure the result. Each section names the record that holds the full reasoning; the requirement IDs are from [hackathon-requirements.md](hackathon-requirements.md).

> [!NOTE]
> Deployed on `prototype` as of 2026-09-30: sign-in, the chat, the entrypoint's checks, the execution record, and a scoped card read through the Gateway. The confirmation, the block, the handoff, the pipeline, and the evaluation are designed in the records and being built; the diagrams show the design.

## The system

One backend on Amazon Bedrock AgentCore: a Runtime serves the chat and runs an explicit LangGraph workflow; a Gateway exposes Lambda tools under Cedar policies; DynamoDB holds every store. Nothing the model writes reaches a tool's `customer_id`, a confirmation, or a handoff's facts ([ADR-0004](adr/0004-agent-architecture-on-agentcore.md)).

```mermaid
flowchart LR
  subgraph Browser["Browser (S3 and CloudFront)"]
    CHAT["/chat: the customer"]
    AGT["/agent: the human agent"]
  end
  COG["Cognito: customers' and staff app clients, pre-token trigger"]
  RT["AgentCore Runtime: entrypoint and graph"]
  GW["AgentCore Gateway: JWT authorizer and Cedar (ENFORCE)"]
  READS["Lambda: read tools"]
  BLOCK["Lambda: block_card"]
  FILE["Lambda: file_handoff"]
  API["Console API: API Gateway and Lambda"]
  DB[("DynamoDB: tools' data, sandbox overlay, confirmations, session bindings, checkpoints, execution records, handoff cases")]
  LLM["Claude Haiku 4.5 (Anthropic API)"]
  PIPE["Pipeline: dbt-duckdb, stamped gold export"]
  COG -.->|"tokens"| Browser
  CHAT -->|"AG-UI, customer token"| RT
  AGT -->|"polls, staff token"| API
  RT -->|"the customer's own token"| GW
  GW --> READS
  GW --> BLOCK
  RT -->|"IAM, off the Gateway"| FILE
  RT -->|"route, extract, write"| LLM
  READS --> DB
  BLOCK --> DB
  FILE --> DB
  RT --> DB
  API --> DB
  PIPE -->|"imported by Terraform"| DB
```

Two layers decide access and actions, and neither trusts the one above it (CTL-04, SEC-05): Cedar checks that every tool call names the customer and the sign-in in the token; each tool checks the rest (the card's status, the confirmation, the window). The graph can route wrongly without a customer seeing another's records, and the model can answer wrongly without a card being blocked unconfirmed. `file_handoff` stays off the Gateway because a customer holding their own token could otherwise file a forged case; the Runtime invokes it with a role no customer holds.

## A turn

```mermaid
sequenceDiagram
  participant C as Chat
  participant A as Runtime authorizer
  participant E as Entrypoint
  participant G as Graph
  participant W as Gateway and Cedar
  participant T as Tool Lambda
  participant R as Execution record
  C->>A: message, access token, thread ID, runtime session ID
  A-->>C: 401 RUN_ERROR when the token is missing, expired, or not a customer's (SEC-04)
  A->>E: verified claims (sub, customer_id, origin_jti)
  E->>E: bind the runtime session to sub, derive the thread key from sub, mask card numbers, turn text sent during a control into a resume
  E->>R: turn opened
  E->>G: run
  G->>W: tool call with the token's customer_id and origin_jti
  W-->>G: denied (-32002) when the call names another customer or sign-in
  W->>T: validated call
  T-->>G: result from the customer's partition and the sign-in's overlay
  G->>R: model calls, tool calls, interrupts, decision
  G-->>C: reply sent whole, or a confirm or handoff control
```

The execution record is the trace, the audit log, and the evaluation's source in one (OPS-01, OPS-02): every model call with its prompt version, tokens, latency, and cost; every tool call; every interrupt and resume; and a decision entry per turn that names the outcome class and what the agent waits for next. Explanations come from it, never from hidden reasoning.

## The graph

A workflow with model steps, not an agent loop (DSN-03, DSN-05): code chooses every node and tool; the model labels a request among eight, extracts among allowed values, writes a reply's words, and writes a handoff's three free-text fields. The policy's rules are the router's labels and the nodes' branches ([the policy](policy/card-support.md), CTL-01).

```mermaid
flowchart TD
  IN(["message or resume"])
  P{"control pending?"}
  ROUTE["route: label, POL-05's order"]
  CARD["resolve_card: which card"]
  READ["read tools"]
  REASON["ask_reason"]
  FIND["find_transaction"]
  CONFIRM["confirm: interrupt with the control"]
  BLOCK["block, then verify by reading back"]
  HANDOFF["handoff: build, validate, file"]
  REPLY["reply, then the reply check"]
  OUT(["events to the chat"])
  IN --> P
  P -->|"no"| ROUTE
  P -->|"confirmation or offer"| CONFIRM
  ROUTE -->|"a card request"| CARD
  ROUTE -->|"unsupported, talk_to_human"| HANDOFF
  ROUTE -->|"no request"| REPLY
  CARD -->|"status, credit, transactions, decline"| READ
  CARD -->|"block_card"| REASON
  CARD -->|"unrecognized_charge"| FIND
  CARD -->|"ambiguous, not active"| HANDOFF
  READ --> REPLY
  REASON --> CONFIRM
  FIND --> CONFIRM
  CONFIRM -->|"confirmed by the control"| BLOCK
  CONFIRM -->|"cancelled or lapsed"| REPLY
  BLOCK -->|"verified"| REPLY
  BLOCK -->|"not verified, or POL-39"| HANDOFF
  HANDOFF --> REPLY
  REPLY --> OUT
```

Three rules make the reply safe to send (AI-03, AI-05, CTL-02):

- **Typed text never confirms.** `confirm` creates a confirmation record and shows a control; only the control's resume, naming that record, confirms or cancels. `block_card` consumes the record in one DynamoDB transaction and reads the card back up to three times; the customer hears "blocked" only when the read-back shows it.
- **Facts as placeholders.** The model writes `{card.expiration}`, never the value; code fills it. Outcomes (blocked, verified, a handoff's reference) are fixed sentences chosen by code.
- **The reply check.** Before a reply leaves, code checks every placeholder, every number, and every withheld field; a reply that fails is replaced by a fixed one built from the same facts, and the fallback is counted (OPS-05).

The handoff is a structured case, not a transcript (CTL-05): the request, each verified fact tied to the tool call that read it, the actions taken, the evidence, and the unresolved questions, validated against [handoff.schema.json](../src/banking_agent/policy/handoff.schema.json) by the graph and again by `file_handoff`, which adds the `is_fraud` facts the model never sees.

## Where each rule holds

| Layer | Decides | Holds even if |
|---|---|---|
| Cognito and the pre-token trigger | Who the customer is; customers get tokens from the customers' app client only, staff from the staff client only | The browser is not ours |
| The Runtime's and the Gateway's JWT authorizers | Only a customer's valid token reaches the agent or a tool | The model is fully compromised |
| The entrypoint | The runtime session belongs to the caller; the thread key derives from the verified `sub`; card numbers are masked before anything reads them | The client sends another customer's IDs |
| Cedar | Every call names the token's `customer_id` and `origin_jti` | The graph routes wrongly |
| The tools | A read returns the customer's partition and never `is_fraud`; a block needs a confirmed, unexpired confirmation for that card and reason | The graph is wrong |
| The graph | Which card, when to ask, when to abstain, decline, or hand off; the retries and the question limit | The model mislabels or misextracts |
| The prompt | Nothing that access or an action depends on | |

## The data

A batch rebuild per pinned snapshot, on the machine that holds it; only the stamped gold export leaves it ([ADR-0002](adr/0002-mirror-dataset-into-pinned-snapshots.md), [ADR-0006](adr/0006-batch-medallion-pipeline.md); DML-01 to DML-06).

```mermaid
flowchart LR
  SNAP[("Pinned snapshot: 13 CSV tables, dataset.lock")]
  BR["Bronze: every row, typed by contract, nothing dropped"]
  SI["Silver: card support at the as-of instant, flagged, split by customer"]
  GO["Gold: what the tools read, last four digits only, 90-day window"]
  EXP[("Gold export, stamped with the snapshot and pipeline version")]
  TD[("Tools' data table")]
  OR["Evaluation oracle"]
  SNAP --> BR --> SI --> GO -->|"make export"| EXP -->|"Terraform import"| TD
  BR --> OR
```

The state the tools read is a frozen master snapshot with an event cutoff: customers and cards as delivered, transactions dated at or before the as-of instant. Rows updated after that instant are flagged, never corrected, and results are reported with and without them.

## How we know it works

Offline, on scripted scenarios played against the deployed system, graded by code against an oracle that applies the policy to the frozen snapshot in code that shares nothing with the tools ([ADR-0005](adr/0005-offline-scenario-evaluation.md); EVL-01 to EVL-14, DML-07 to DML-12).

```mermaid
flowchart LR
  GEN["Generator: held-out customers and request families, both languages"]
  CASES[("Held-out cases, manifest hash committed")]
  CUST["Scripted customer: reacts to decision entries and controls, never to prose"]
  SYS["Faro on the deployed stack"]
  BASE["Deterministic baseline: keyword router, templates"]
  REC[("Execution records, streams, filed cases")]
  ORC["Oracle: the policy over bronze"]
  GRADE["Grader: code first; a validated judge for wording only"]
  REP["Report: M-01 to M-05, per language and segment, failures included, every number labeled offline"]
  GEN --> CASES --> CUST
  CUST --> SYS --> REC
  CUST --> BASE --> REC
  REC --> GRADE
  ORC --> GRADE --> REP
```

The split holds by customer (the MD5 rule shared with the analysis), by authored request family, and by time (DML-09). Held-out cases include incorrect and missing data, expired sessions, unauthorized access, prompt injection, tool failures, and multilingual ambiguity, and the same cases run against the baseline. Zero unsafe outcomes in a small set bounds the rate; it never proves it zero (M-04).

## Where the reasoning lives

| Record | Decides |
|---|---|
| [ADR-0003](adr/0003-choose-workflow-from-evidence.md) | Card support, from the [selection report](analysis/selection.md) |
| [ADR-0004](adr/0004-agent-architecture-on-agentcore.md) | The agent, the tools, the stores, the confirmation, the handoff, operations |
| [ADR-0005](adr/0005-offline-scenario-evaluation.md) | The evaluation, the oracle, the baseline, the judge, reporting |
| [ADR-0006](adr/0006-batch-medallion-pipeline.md) | The pipeline, its contracts and checks, freshness, lineage |
| [ADR-0007](adr/0007-role-gated-web-app.md) | The web app, sign-in, the console API, handoffs as cases |
| [The policy](policy/card-support.md) | What Faro answers, does, refuses, and hands off, one ID per rule |
