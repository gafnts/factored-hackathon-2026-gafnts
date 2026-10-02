<h1 align="center">Faro</h1>
<p align="center">
  <strong>LATAM Bank's card support agent, in Spanish and Portuguese, that acts only when the cardholder confirms and knows when to hand off to a person.</strong>
</p>
<p align="center">
<a href="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/quality-gates.yml"><img src="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/quality-gates.yml/badge.svg" alt="Quality gates"></a>
<a href="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/deploy-prototype.yml"><img src="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/deploy-prototype.yml/badge.svg" alt="Deploy prototype"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License"></a>
</p>

---

<p align="center">Built for the Factored AI &amp; Data Hackathon 2026. In Spanish, <em>faro</em> is a lighthouse; in Portuguese, <em>ter faro</em> is to have a nose for things. Guidance in one language, judgment in the other: Faro grounds every answer in the cardholder's own records, enforces permissions in code rather than in the prompt, and gives a human agent a structured case file whenever a request needs one.</p>

## Contents

- [The story](#the-story)
- [What sets Faro apart](#what-sets-faro-apart)
- [Documentation](#documentation)
- [Quick start](#quick-start)
- [Repository layout](#repository-layout)

---

## The story

A LATAM Bank customer spots a purchase on their credit card that they didn't make, and writes to the bank's chat in Portuguese: *Não reconheço uma compra no meu cartão.*

Faro finds the charge among the card's transactions and offers to block the card. It won't act on a typed *sim*: the chat shows a button that names the card and the reason, and only that button confirms. Once the customer presses it, the tool reads the card back, and Faro says the card is blocked only because that read shows it. Then it files the case to dispute intake and gives the customer a reference.

In another tab, a human agent sees the case arrive within seconds: the request, each verified fact next to the tool call that read it, the verified block, and the customer's own words kept apart from the facts. There is no transcript to read back and nothing to ask the customer twice. Had the customer cancelled the block, the same case would have arrived marked urgent.

> [!NOTE]
> LATAM Bank and every customer in it are synthetic, from the organizers' dataset. This is the journey our design sets out ([ADR-0007](docs/adr/0007-role-gated-web-app.md#judges-access)); the build is under way.

---

## What sets Faro apart

- **A lighthouse doesn't steer the ship.** Faro shows what the records say and proposes the one action it can take; the customer's button decides, and typed text never does.
- **Judgment in code, not in the prompt.** The tools and Cedar decide every access and action, so a fully compromised model still can't read another customer's card or block one unconfirmed.
- **Done means verified.** A block is reported only after the card is read back, and handed to a person when the read doesn't show it.
- **Candid about its records.** A missing field is reported as not recorded, and conflicting records are stated side by side, never reconciled.
- **Graded by an independent oracle.** Expected outcomes come from the policy applied to the frozen bank, in code that shares nothing with Faro's tools, and held-out results are reported against a deterministic baseline, failures included.

---

## Documentation

### Product

- [brief.md](docs/product/brief.md): the problem, who Faro serves, what it refuses to do, and the outcomes we intend
- [identity.md](docs/product/identity.md): Faro's name, voice, and look

### Design

- [prerequisites.md](docs/prerequisites.md): what the organizers evaluate, with the IDs every document cites
- [card-support.md](docs/policy/card-support.md): the policy Faro follows (synthetic), one ID per rule
- [architecture.md](docs/architecture.md): the system on one page, with its diagrams
- [docs/adr/](docs/adr/README.md): the architecture decision records, from the workflow choice to the web app

### Data

- [docs/analysis/](docs/analysis/): the profiling, traffic, workflow selection, and card support reports, rebuilt by `make analysis`
- [pipeline/](pipeline/README.md): the dbt project that builds the tools' data from the snapshot, with each export's manifest in [docs/pipeline/](docs/pipeline/)
- [dataset.lock](dataset.lock): the pinned dataset snapshot every run reads

---

## Quick start

With the [toolchain](CONTRIBUTING.md#1-install-the-toolchain) installed, set up the Python dependencies, the pre-commit hooks, and the tflint plugins:

```bash
make install
```

Then run every quality gate against every file, exactly as CI does:

```bash
make check
```

> [!NOTE]
> Changing code needs no AWS access. Working with the dataset or deploying your own copy of the stack takes a few more steps; [CONTRIBUTING.md](CONTRIBUTING.md#pick-your-path) maps each goal to them.

---

## Repository layout

| Path | Contents |
|---|---|
| [src/banking_agent/](src/banking_agent/) | The Python package |
| [pipeline/](pipeline/README.md) | The dbt project: bronze, silver, and gold from the pinned snapshot |
| [tests/](tests/) | Pytest suite |
| [infra/](infra/) | Terraform: the service stack per environment, the IAM bootstrap, and the dataset bucket |
| [scripts/](scripts/) | Account bootstrap, teardown, and setup checks |
| [Makefile](Makefile) | Every command; `make help` lists them |
