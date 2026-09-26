# ADR-0002: Mirror the organizer dataset into pinned snapshots

## Status

Proposed (2026-09-26).

## Context

[ADR-0001](0001-deploy-to-us-east-1.md) puts every stack in us-east-1, while the dataset stays in the organizers' bucket in us-east-2. Five forces shape how the project should read it:

- **The dataset sits in another account, behind shared keys.** The bucket belongs to the organizers' account (157725502942) in us-east-2 and is readable with one IAM user's access keys, printed in the dataset dictionary with a request not to share them beyond participants. Reading it at runtime would put those keys in CI and in the deployed demo, and the demo would break the day they are rotated or revoked, which may happen once the event ends.
- **The source changes.** On 2026-09-26, `data/` held 7,671 CSV files (5.35 GB): six dimension and reference tables as single files, and seven fact tables partitioned as `year=/month=/day=` (1,097 days each, 1,083 for `campaign_sends`). Next to it, `data_backup_20260831/` holds an earlier publication in which `customers.csv`, `products.csv`, and `service_agents.csv` differ in size, and `call_transcripts` and `satisfaction_surveys` are missing. The dictionary also announces late-arriving partitions and schema changes.
- **Past versions can't be recovered from the source.** The reader key can list and download objects and see their ETags, but not read the bucket's configuration, so a version we didn't keep may be gone for good.
- **A server-side copy is impossible.** Copying between buckets in different accounts needs one principal allowed on both, which would take changes to the organizers' IAM or bucket policy. The bytes have to stream through something that holds both sets of credentials.
- **The scoring rewards stable inputs.** Data preparation must be repeatable (DML-01), with lineage (DML-04) and a freshness policy (DML-05); baseline and proposed system must run on the same held-out workload (EVL-01); credentials stay out of the public repository (SEC-03); and setup must be reproducible (OPS-07).

## Decision

Copy the organizers' `data/` prefix into a bucket this project owns in us-east-1, and use the organizers' keys for that copy only. Everything downstream (ETL, evaluation, CI, the deployed demo) reads the copy with the project's own roles.

Each copy is an immutable snapshot, and a lock file committed to the repository pins the snapshot the code uses. When the source no longer matches the lock, the copy stops and reports the difference; new data is adopted deliberately, through a reviewed change to the lock. Re-running a copy that already matches transfers nothing, and pipeline outputs and evaluation reports record the snapshot they ran on.

The bucket lives outside the per-environment stacks, so destroying an environment never deletes the data.

## Alternatives considered

**Read the organizers' bucket directly.** No copy to maintain, but the shared keys would have to live in CI and in the deployed demo, every read would cross accounts and regions, and nothing would stop the data from changing under a running evaluation.

**Copy once and never again.** A run-once guard either misses late-arriving partitions or, the first time someone forces a re-sync, silently changes the evaluation baseline. A lock makes both cases visible.

**Keep the data only on laptops.** `aws s3 sync` into `./data/` is the quickest start, but CI and the demo can't read a laptop, and two people can end up holding different bytes with nothing to tell them apart. A local copy is still useful for exploration, as long as it comes from the pinned snapshot.

**Pin object versions instead of copying snapshots.** Versioning plus a list of version IDs would pin the data without storing a second copy, but DuckDB and Athena read paths, not version IDs, and an extra 5 GB snapshot costs a few cents a month.

**Server-side copy tools.** `aws s3 sync` between buckets, S3 Replication, S3 Batch Operations, and DataSync all need a grant on the source bucket that only the organizers could give.

## Consequences

Positive:
- The organizers' keys are needed only where the copy runs; nothing deployed and nothing in the repository holds them.
- The demo and every pipeline keep working if those keys are rotated or revoked.
- Every run reads the same bytes until the lock changes, and a change to the data arrives as a PR like any other change.
- Pipelines read in-region, from the same Region ADR-0001 chose for everything else.
- The snapshot ID traces a number in an evaluation report back to the exact raw files.

Negative:
- A copy streams about 5.35 GB through the machine running it, down and then up: minutes on a datacenter link, tens of minutes on a home connection.
- More moving parts than reading the source directly: a bucket, a copy module, and a lock file.
- Each snapshot duplicates the dataset in storage, at a few cents a month.
- A clone in another account can rebuild the locked snapshot only while the organizers still publish the same bytes. Otherwise the lock check fails loudly, and the difference has to be reported as a data limitation (SCP-07).
- Teardown gains a step: the bucket holding the snapshots has to be emptied before it can be deleted.
