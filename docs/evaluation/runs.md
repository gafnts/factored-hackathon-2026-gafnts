# Runs

Generated from the files under `runs/` by `make eval-index`; do not edit. One row per reported run
(ADR-0005, The run manifest), each an offline measurement on our cases; the per-case results that a
manifest's hashes name stay in the evaluation bucket.

| Run | Date | Purpose | Mode | Set (cases) | Stack | Grader | Passed | Cost (USD) |
|---|---|---|---|---|---|---|---|---|
| 20261001T224049Z-a707 | 2026-10-01 | The live check after promotion 3: a block, the handoff with an injected merchant, a fault that recovers, a built fixture, and the access attempt's first play against a deployed stack, in both languages. | end_to_end | selection (12) | prototype | 4 | 8 of 12 | 0.03 |
| 20261003T040648Z-da8b | 2026-10-03 | The pilot before the freeze (ADR-0005, Budget and the pilot), on the clean tree after promotion 4: 24 selection cases on prototype at parallel 2, with confirmations (a typed yes, a cancelled block), handoffs (a person asked for, a customer who isn't active), both direct-access attempts, two faults (a read that recovers, a block that doesn't verify), and the which-card question, in both languages; its cost and time per case project the held-out plan. | end_to_end | selection (24) | prototype | 5 | 24 of 24 | 0.10 |
