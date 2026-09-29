# Documentation

What we decided about Faro, why, and the evidence behind it. Every document cites the requirement IDs in [hackathon-requirements.md](hackathon-requirements.md), and the policy's rule IDs wherever a rule applies.

| Path | Holds |
|---|---|
| [product/](product/) | The [product brief](product/brief.md), covering the problem, who Faro serves, and the outcomes we intend; and the [identity guide](product/identity.md), covering Faro's name, voice, and look |
| [policy/](policy/) | The [card support policy](policy/card-support.md): what Faro answers, does, and refuses, one ID per rule (synthetic) |
| [adr/](adr/README.md) | The architecture decision records and their index |
| [analysis/](analysis/) | The profiling, traffic, workflow selection, and card support reports, each with its JSON, computed from the pinned snapshot by `make analysis` |
| [hackathon-requirements.md](hackathon-requirements.md) | Everything the organizers evaluate, with stable requirement IDs |

## Reading order

1. [The product brief](product/brief.md): what Faro is for.
2. [ADR-0003](adr/0003-choose-workflow-from-evidence.md) and the [selection report](analysis/selection.md): why card support.
3. [The policy](policy/card-support.md): the rules Faro follows.
4. [ADR-0004](adr/0004-agent-architecture-on-agentcore.md): what runs where, and what enforces each rule.
5. [ADR-0005](adr/0005-offline-scenario-evaluation.md): how we know it works.
6. [ADR-0006](adr/0006-batch-medallion-pipeline.md) and [ADR-0007](adr/0007-role-gated-web-app.md): the data pipeline and the web app.
