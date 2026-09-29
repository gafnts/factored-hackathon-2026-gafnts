# Architecture Decision Records

This directory records the significant architectural decisions made in this project. Each ADR captures the context, the options considered, and the reasoning behind the choice, so future contributors understand not just what was decided, but why, and what tradeoffs were accepted.

## Naming conventions

| Element | Rule |
|---|---|
| File name | `NNNN-short-slug.md`: a few words from the title in kebab case, without articles, e.g. `0004-agent-architecture-on-agentcore.md` |
| Number | 4-digit zero-padded integer, assigned sequentially (`0001`, `0002`, …) |
| Title | A formal phrase that names the decision itself (what is chosen, and for what), as a noun phrase or an imperative, e.g. `Offline scenario evaluation against an independent policy oracle` or `Choose the workflow from evidence` |
| Status | `Proposed` → `Accepted` → `Deprecated` / `Superseded by ADR-NNNN` |

> [!NOTE]
> When a decision is reversed or replaced, mark the old ADR as `Superseded by ADR-NNNN` and link forward. Never delete an ADR.

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

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-deploy-to-us-east-1.md) | Deploy to us-east-1 | Accepted |
| [0002](0002-mirror-dataset-into-pinned-snapshots.md) | Mirror the organizer dataset into pinned snapshots | Accepted |
| [0003](0003-choose-workflow-from-evidence.md) | Choose the workflow from evidence | Accepted |
| [0004](0004-agent-architecture-on-agentcore.md) | Explicit LangGraph agent on AgentCore, with policy enforced in Gateway tools and Cedar | Proposed |
| [0005](0005-offline-scenario-evaluation.md) | Offline scenario evaluation against an independent policy oracle | Proposed |
| [0006](0006-batch-medallion-pipeline.md) | Batch medallion pipeline in dbt-duckdb, exported per snapshot to the tools' store | Proposed |
| [0007](0007-role-gated-web-app.md) | Role-gated web app on one CloudFront origin, with a polled handoff console | Proposed |
