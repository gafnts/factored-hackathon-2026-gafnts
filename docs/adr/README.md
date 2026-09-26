# Architecture Decision Records

This directory records the significant architectural decisions made in this project. Each ADR captures the context, the options considered, and the reasoning behind the choice, so future contributors understand not just what was decided, but why, and what tradeoffs were accepted.

## Naming conventions

| Element | Rule |
|---|---|
| File name | `NNNN-kebab-case-title.md` |
| Number | 4-digit zero-padded integer, assigned sequentially (`0001`, `0002`, …) |
| Title | Short imperative phrase describing the decision (verb + noun), e.g. `use-event-driven-pipeline` |
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
