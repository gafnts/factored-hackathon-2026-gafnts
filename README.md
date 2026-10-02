<p align="center">
  <a href="https://faro.gabriel.com.gt"><img src="docs/images/banner.png" alt="Faro" width="100%"></a>
</p>
<p align="center">
  <strong>A card support agent for LATAM Bank, in Spanish and Portuguese. <br>
  It explains what the records say, blocks a card only when its holder confirms, and hands off to a person with a structured case file.</strong>
</p>
<p align="center">
  <a href="#introduction"><strong>Introduction</strong></a> ·
  <a href="#architecture"><strong>Architecture</strong></a> ·
  <a href="#evaluation"><strong>Evaluation</strong></a> ·
  <a href="#limitations"><strong>Limitations</strong></a> ·
  <a href="#self-hosting"><strong>Self-hosting</strong></a> ·
  <a href="#contributing"><strong>Contributing</strong></a>
</p>
<p align="center">
  <a href="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/quality-gates.yml"><img src="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/quality-gates.yml/badge.svg" alt="Quality gates"></a>
  <a href="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/deploy-prototype.yml"><img src="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/deploy-prototype.yml/badge.svg" alt="Deploy prototype"></a>
  <a href="https://faro.gabriel.com.gt"><img src="https://img.shields.io/website?url=https%3A%2F%2Ffaro.gabriel.com.gt&label=prototype&up_message=live&down_message=down" alt="Prototype"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License"></a>
</p>

---

## Introduction

Built for the Factored AI &amp; Data Hackathon 2026. In Spanish, *faro* is a lighthouse; in Portuguese, *ter faro* is to have a nose for things. Guidance in one language, judgment in the other: Faro grounds every answer in the cardholder's own records, enforces permissions in code rather than in the prompt, and gives a human agent a structured case file whenever a request needs one.

A LATAM Bank customer spots a purchase on their credit card that they didn't make, and writes to the bank's chat in Portuguese: *Não reconheço uma compra no meu cartão.*

Faro finds the charge among the card's transactions and offers to block the card. It won't act on a typed *sim*: the chat shows a button that names the card and the reason, and only that button confirms. Once the customer presses it, the tool reads the card back, and Faro says the card is blocked only because that read shows it. Then it files the case to dispute intake and gives the customer a reference.

In another tab, a human agent sees the case arrive within seconds: the request, each verified fact next to the tool call that read it, the verified block, and the customer's own words kept apart from the facts. There is no transcript to read back and nothing to ask the customer twice. Had the customer cancelled the block, the same case would have arrived marked urgent.

<p align="center">
  <a href="https://faro.gabriel.com.gt"><img src="docs/images/chat.png" alt="The chat, before the first message" width="100%"></a>
</p>

> [!NOTE]
> LATAM Bank and every customer in it are synthetic, from the organizers' dataset. This journey runs end to end on the prototype, and the browser suite plays it, in Portuguese, against every deployed stack it checks ([ADR-0007](docs/adr/0007-role-gated-web-app.md#judges-access)).

What sets Faro apart:

- **A lighthouse doesn't steer the ship.** Faro shows what the records say and proposes the one action it can take; the customer's button decides, and typed text never does.
- **Judgment in code, not in the prompt.** The tools and Cedar decide every access and action, so a fully compromised model still can't read another customer's card or block one unconfirmed.
- **Done means verified.** A block is reported only after the card is read back, and handed to a person when the read doesn't show it.
- **Candid about its records.** A missing field is reported as not recorded, and conflicting records are stated side by side, never reconciled.
- **Graded by an independent oracle.** Expected outcomes come from the policy applied to the frozen bank, in code that shares nothing with Faro's tools, and results are reported with their failures.

The [product brief](docs/product/brief.md) says who Faro serves and what it refuses to do; the [policy](docs/policy/card-support.md) holds every rule it follows, one ID per rule; [docs/](docs/README.md) indexes the rest.

---

## Architecture

One backend on Amazon Bedrock AgentCore. A Runtime serves the chat and runs an explicit LangGraph workflow: code chooses every step and tool, and the model only labels, extracts, and writes words around placeholders that code fills. A Gateway exposes the banking tools as Lambda functions under Cedar policies, so every call must name the customer and the sign-in in the token. DynamoDB holds every store, and a dbt pipeline builds the tools' data from a pinned snapshot of the bank.

<p align="center">
  <img src="docs/images/architecture.png" alt="The system" width="100%">
</p>

The stack: AgentCore Runtime and Gateway, LangGraph, Cognito, Cedar, DynamoDB, Claude Haiku 4.5, dbt with DuckDB, React with assistant-ui, and Terraform for all of it.

[architecture.md](docs/architecture.md) is the system on one page: a turn, the graph, where each rule holds, the data, and the evaluation. The [architecture decision records](docs/adr/README.md) hold the reasoning, from the choice of workflow to the web app.

---

## Evaluation

Faro is evaluated offline, on scripted conversations played against the deployed stack and graded by code. Expected outcomes come from an oracle that applies the policy to the frozen bank through its own code, so a bug in Faro's tools shows up as a disagreement rather than agreeing with itself. The cases are drawn from request families we wrote, in both languages, with a third of the families and a fifth of the customers held out and never read during development. Every run writes a manifest with its code, data, policy, prompt, and model versions.

<p align="center">
  <img src="docs/images/evaluation.png" alt="The evaluation" width="100%">
</p>

What exists today:

- [families.md](docs/evaluation/families.md): the requests the scripted customer sends, and how they were written and split.
- [disagreements.md](docs/evaluation/disagreements.md): where the system and the oracle differ, each triaged in writing.
- [runs.md](docs/evaluation/runs.md): every reported run, with its grader version and headline numbers.

The held-out run against a deterministic baseline, with M-01 to M-05 per language and segment, is still to come; its report lands here, labeled as an offline measurement. The design is in [ADR-0005](docs/adr/0005-offline-scenario-evaluation.md).

---

## Limitations

The bank is synthetic, and it shows: contacts can't be tied to a workflow, no supplied label carries signal, about half of all active cards are past their expiration date and still transact, and about 5% of each core field is missing at random. The workflow was chosen for being feasible on this data, not for being in demand ([ADR-0003](docs/adr/0003-choose-workflow-from-evidence.md)). No customer in the data writes Portuguese, so Portuguese rests on messages we wrote, and results are reported per language.

Three pieces are designed and not built, each a stated limitation: a handoff filed after a confirmation's deadline when the customer has left, claim and resolve in the console, and the AI team's page. The tools mock the bank's systems of record over a frozen snapshot; what they stand for, and what replacing them would take, is in [ADR-0004](docs/adr/0004-agent-architecture-on-agentcore.md#the-tools-as-the-seam-to-the-banks-systems) and [ADR-0007](docs/adr/0007-role-gated-web-app.md#in-a-bank-ops-11). The evaluation report gathers the full account, with the remaining deployment work and risks, when it lands.

---

## Self-hosting

A fork stands up in an AWS account you control, with Terraform and nothing tied to our accounts. Most contributions need no AWS access at all:

| You want to | You need |
|---|---|
| Change code, tests, or docs | Only the toolchain |
| Explore or process the organizers' dataset | The read-only keys from the dataset dictionary |
| Run the whole stack in your own AWS account | Admin access to an AWS account, and your own fork |

With the [toolchain](CONTRIBUTING.md#1-install-the-toolchain) installed:

```bash
make install   # Python and web deps, pre-commit hooks, tflint plugins
make check     # Every quality gate against every file, exactly as CI does
```

[CONTRIBUTING.md](CONTRIBUTING.md) takes it from there: the dataset snapshot, the pipeline, the deploy roles, the `local` and `prototype` environments, and teardown.

---

## Contributing

Feature branches merge into `develop`, which runs the quality gates and deploys nothing. `main` mirrors what is live on the prototype and only accepts merges from `develop`. Commit subjects are imperative, PRs cite the requirement IDs they cover, and a decision someone could question later gets an architecture decision record. The [contributing guide](CONTRIBUTING.md#day-to-day-workflow) has the details, and `make help` lists every command.
