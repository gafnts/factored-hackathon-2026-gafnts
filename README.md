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
- [Quick start](#quick-start)
- [Repository layout](#repository-layout)
- [Documentation](#documentation)

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

The [product brief](docs/product.md) says who Faro serves, what it refuses to do, and the outcomes we intend; the [card support policy](docs/policy/card-support.md) holds the rules it follows.

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
| [tests/](tests/) | Pytest suite (integration tests are marked and deselected by default) |
| [infra/](infra/) | Terraform service stack, one state file per environment (`local` and `prototype`) |
| [infra/iam/](infra/iam/) | One-time IAM bootstrap: the deploy roles for each environment |
| [infra/dataset/](infra/dataset/) | The bucket holding the pinned dataset snapshots, outside every environment |
| [scripts/](scripts/) | Account bootstrap, teardown, and setup checks, run through `make` |
| [docs/](docs/) | Requirements catalogue, product brief and identity guide, architecture decision records, the card support policy, and the dataset analysis reports |
| [.github/workflows/](.github/workflows/) | Quality gates and the `prototype` deploy pipeline |
| [dataset.lock](dataset.lock) | The pinned dataset snapshot every run reads ([ADR-0002](docs/adr/0002-mirror-dataset-into-pinned-snapshots.md)) |
| [Makefile](Makefile) | Every setup, quality, and deploy command (`make help` lists them) |

---

## Documentation

- [product.md](docs/product.md): the product brief, covering the problem, who Faro serves, what it does and refuses to do, and the outcomes we intend
- [identity.md](docs/identity.md): Faro's name, personality, voice in Spanish and Portuguese, and visual identity
- [CONTRIBUTING.md](CONTRIBUTING.md): setup paths by goal, environments and guardrails, day-to-day workflow, troubleshooting, and teardown
- [hackathon-requirements.md](docs/hackathon-requirements.md): every point the organizers evaluate, with stable requirement IDs that code, tests, and PRs cite
- [docs/adr/](docs/adr/README.md): architecture decision records, from the deployment region to the agent's architecture, its evaluation, the data pipeline, and the web app
- [card-support.md](docs/policy/card-support.md): the card support policy (synthetic), whose rule IDs tests, evaluation cases, and handoffs cite
