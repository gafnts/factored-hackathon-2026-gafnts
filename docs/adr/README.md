# Architecture Decision Records

This directory records the significant architectural decisions made in this project. Each ADR captures the context, the options considered, and the reasoning behind the choice, so future contributors understand not just what was decided, but why, and what tradeoffs were accepted.

## Naming conventions

| Element | Rule |
|---|---|
| File name | `NNNN-short-slug.md`: a few words from the title in kebab case, without articles, e.g. `0004-agent-architecture-on-agentcore.md` |
| Number | 4-digit zero-padded integer, assigned sequentially (`0001`, `0002`, …) |
| Title | A formal phrase that names the decision itself (what is chosen, and for what), as a noun phrase or an imperative, e.g. `Offline scenario evaluation against an independent policy oracle` or `Choose the workflow from evidence` |
| Status | `Proposed` → `Accepted` → `Deprecated` / `Superseded by ADR-NNNN`; an accepted ADR can also be `Amended by ADR-NNNN` |

> [!NOTE]
> When a decision is reversed or replaced, mark the old ADR as `Superseded by ADR-NNNN` and link forward. When a later ADR corrects part of an accepted one, the earlier ADR stays accepted and is marked `Amended by ADR-NNNN`, with a link to the correction. Never delete an ADR.

A proposed ADR may leave decisions open: each is marked **Open** where it arises and listed under Open decisions with the option we lean towards. Accepting the ADR settles them, and the list becomes Settled at acceptance, each item stating the choice and any alternative not taken.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-deploy-to-us-east-1.md) | Deploy to us-east-1 | Accepted |
| [0002](0002-mirror-dataset-into-pinned-snapshots.md) | Mirror the organizer dataset into pinned snapshots | Accepted |
| [0003](0003-choose-workflow-from-evidence.md) | Choose the workflow from evidence | Accepted; amended by ADR-0004 |
| [0004](0004-agent-architecture-on-agentcore.md) | Explicit LangGraph workflow on AgentCore, with policy enforced in Gateway tools and Cedar | Accepted; amended 2026-09-29 (decision 7 deferred, the chat's request, the customer's status in cases, Haiku 4.5 without the grid, the model key in our own secret, `is_fraud` kept from the read tools' role, the entrypoint's checks as built) |
| [0005](0005-offline-scenario-evaluation.md) | Offline scenario evaluation against an independent policy oracle | Accepted; amended 2026-09-29 (no deadline cases, outcome classes, no model grid); amended 2026-09-30 (no in-process mode) |
| [0006](0006-batch-medallion-pipeline.md) | Batch medallion pipeline in dbt-duckdb, exported per snapshot to the tools' store | Accepted; amended 2026-09-29 (a tiny export before the pipeline) |
| [0007](0007-role-gated-web-app.md) | Role-gated web app on one CloudFront origin, with a polled handoff console | Accepted; amended 2026-09-29 (the site's own origin in the content security policy); amended 2026-09-30 (claim and resolve deferred, no `/ops` page) |

## Template

```markdown
# ADR-NNNN: Title

## Status

Proposed (YYYY-MM-DD).

## Context

The forces at play: the problem, the constraints, and the evidence that makes a decision necessary.

## Decision

What we will do, stated in full sentences.

## Alternatives considered

Each option that was on the table and why it lost.

## Consequences

Positive:
- ...

Negative:
- ...
```
