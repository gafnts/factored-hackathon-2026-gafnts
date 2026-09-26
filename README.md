<h1 align="center">factored-hackathon-2026-gafnts</h1>
<p align="center">
  <strong>Fully functional production-ready AI-first banking agent capable of handling complex user interactions.</strong>
</p>
<p align="center">
<a href="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/checks.yml"><img src="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/checks.yml/badge.svg" alt="Quality gates"></a>
<a href="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/deploy-demo.yml"><img src="https://github.com/gafnts/factored-hackathon-2026-gafnts/actions/workflows/deploy-demo.yml/badge.svg" alt="Deploy demo"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License"></a>
</p>

---

<p align="center">An AI-first customer service system for a regional LATAM bank, built for the Factored AI & Data Hackathon 2026. The goal is a system that understands customer requests in Spanish and Portuguese, grounds its answers in permitted account, transaction, and policy data, and hands off to a human agent when it should not act alone.</p>

## Contents

- [Status](#status)
- [Repository layout](#repository-layout)
- [Getting started](#getting-started)
- [Documentation](#documentation)

---

## Status

The repository is bootstrapped: Python tooling, quality gates, CI, and a Terraform skeleton for two AWS environments (`local` and the hosted `demo`) are in place. The agent itself, its data pipeline, and its evaluation harness are not implemented yet.

---

## Repository layout

| Path | Contents |
|---|---|
| [src/banking_agent/](src/banking_agent/) | The Python package |
| [tests/](tests/) | Pytest suite (integration tests are marked and deselected by default) |
| [infra/](infra/) | Terraform service stack, one state file per environment |
| [infra/iam/](infra/iam/) | One-time IAM bootstrap: deploy roles for `local` and `demo` |
| [scripts/](scripts/) | Account bootstrap, teardown, and setup checks, run through `make` |
| [docs/adr/](docs/adr/) | Architecture decision records |
| [.github/workflows/](.github/workflows/) | Quality gates and the `demo` deploy pipeline |

---

## Getting started

Install the Python dependencies, the pre-commit hooks, and the tflint plugins:

```bash
make install
```

Then run every quality gate against every file:

```bash
make check
```

> [!NOTE]
> Changing code needs no AWS access. Working with the dataset or deploying your own copy of the stack takes a few more steps; [CONTRIBUTING.md](CONTRIBUTING.md#pick-your-path) maps each goal to them.

---

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md): setup paths by goal, environments and guardrails, day-to-day workflow, troubleshooting, and teardown
- [docs/hackathon-requirements.md](docs/hackathon-requirements.md): every point the organizers will evaluate, with stable requirement IDs
- [docs/adr/README.md](docs/adr/README.md): architecture decision records and the template for new ones
