<h1 align="center">Bilingual Banking Service Agent</h1>
<p align="center">
  <strong>Customer service in Spanish and Portuguese that resolves what it can verify, asks when a request is unclear, and hands off when it should not act.</strong>
</p>
<p align="center">
<a href="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/quality-gates.yml"><img src="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/quality-gates.yml/badge.svg" alt="Quality gates"></a>
<a href="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/deploy-prototype.yml"><img src="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/deploy-prototype.yml/badge.svg" alt="Deploy prototype"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License"></a>
</p>

---

<p align="center">A customer service system for a regional LATAM bank, built for the Factored AI & Data Hackathon 2026. It is designed to understand requests in Spanish and Portuguese, ground every answer in permitted account, transaction, and policy data, enforce permissions in code rather than in the prompt, and give a human agent a structured case file whenever a request needs one.</p>

## Contents

- [Quick start](#quick-start)
- [Repository layout](#repository-layout)
- [Documentation](#documentation)

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
| [docs/](docs/) | Requirements catalogue, architecture decision records, the card support policy, and the dataset analysis reports |
| [.github/workflows/](.github/workflows/) | Quality gates and the `prototype` deploy pipeline |
| [dataset.lock](dataset.lock) | The pinned dataset snapshot every run reads ([ADR-0002](docs/adr/0002-mirror-dataset-into-pinned-snapshots.md)) |
| [Makefile](Makefile) | Every setup, quality, and deploy command (`make help` lists them) |

---

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md): setup paths by goal, environments and guardrails, day-to-day workflow, troubleshooting, and teardown
- [hackathon-requirements.md](docs/hackathon-requirements.md): every point the organizers evaluate, with stable requirement IDs that code, tests, and PRs cite
- [docs/adr/](docs/adr/README.md): architecture decision records, from the deployment region to the agent's architecture, its evaluation, the data pipeline, and the web app
- [card-support.md](docs/policy/card-support.md): the card support policy (synthetic), whose rule IDs tests, evaluation cases, and handoffs cite
