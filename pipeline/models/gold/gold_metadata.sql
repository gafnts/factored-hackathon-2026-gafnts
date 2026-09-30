-- The frozen bank's clock and the snapshot it was read from, which every tool result returns (ADR-0004, Two clocks).
select
    '{{ var("snapshot_id") }}' as snapshot_id,
    '{{ var("pipeline_version") }}' as pipeline_version,
    business_date,
    as_of
from {{ ref('silver_clock') }}
