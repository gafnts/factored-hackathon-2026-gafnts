# Documentation

What we decided about Faro, why, and the evidence behind it. Every document cites the requirement IDs in [prerequisites.md](prerequisites.md), and the policy's rule IDs wherever a rule applies.

| Path | Holds |
|---|---|
| [adr/](adr/README.md) | The architecture decision records and their index |
| [architecture.md](architecture.md) | The system on one page: what runs where, a turn, the graph, where each rule holds, the data, and the evaluation |
| [evaluation/](evaluation/) | The request [families](evaluation/families.md), the [disagreement log](evaluation/disagreements.md), the [run index](evaluation/runs.md), and the manifests of the sets and the reported runs |
| [analysis/](analysis/) | The profiling, traffic, workflow selection, and card support reports, each with its JSON, computed from the pinned snapshot by `make analysis` |
| [pipeline/](pipeline/) | The manifest of each gold export, from `make export`: the stamp, the clock, rows per model, content hashes, and every check's result ([the pipeline](../pipeline/README.md)) |
| [policy/](policy/) | The [card support policy](policy/card-support.md): what Faro answers, does, and refuses, one ID per rule (synthetic) |
| [product/](product/) | The [product brief](product/brief.md), covering the problem, who Faro serves, and the outcomes we intend; and the [identity guide](product/identity.md), covering Faro's name, voice, and look |
| [prerequisites.md](prerequisites.md) | Everything the organizers evaluate, with stable requirement IDs |
| `hackathon/` | The organizers' materials, including the dataset keys (gitignored) |

## Reading order

1. [The product brief](product/brief.md): what Faro is for.
2. [ADR-0003](adr/0003-choose-workflow-from-evidence.md) and the [selection report](analysis/selection.md): why card support.
3. [The policy](policy/card-support.md): the rules Faro follows.
4. [The architecture](architecture.md): the whole system on one page.
5. [ADR-0004](adr/0004-agent-architecture-on-agentcore.md): what runs where, and what enforces each rule.
6. [ADR-0005](adr/0005-offline-scenario-evaluation.md): how we know it works.
7. [ADR-0006](adr/0006-batch-medallion-pipeline.md) and [ADR-0007](adr/0007-role-gated-web-app.md): the data pipeline and the web app.
