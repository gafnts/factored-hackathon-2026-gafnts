{# The checks dbt doesn't ship. Each returns one row per failing file or value, with n_records rows behind it. #}

{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n_records
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

{# Every row sits in its processing day's partition, and happened that day or within the days after it that the contract allows. #}
{% test processed_on_its_day(model, event_date, days_after, via=none, parent=none, parent_date=none) %}
with events as (
    {% if via %}
    select m.source_file, m.process_date, p.{{ parent_date }} as happened
    from {{ model }} m
    left join {{ parent }} p on p.{{ via }} = m.{{ via }}
    {% else %}
    select source_file, process_date, {{ event_date }} as happened
    from {{ model }}
    {% endif %}
)
select source_file as key, count(*) as n_records
from events
where process_date is distinct from {{ partition_date('source_file') }}
    or (happened is not null and happened::date - process_date not between 0 and {{ days_after }})
group by source_file
{% endtest %}

{# Bronze read exactly the lock's files, in both directions; a file with no records has no rows to show it was read. #}
{% test files_match_the_lock(model, table) %}
with locked as (
    select key
    from {{ source('checks', 'lock_files') }}
    join {{ source('checks', 'record_counts') }} using (key)
    where {{ files_of(table) }} and records > 0
),
read as (
    select distinct source_file as key from {{ model }}
)
select coalesce(locked.key, read.key) as key
from locked
full join read on locked.key = read.key
where locked.key is null or read.key is null
{% endtest %}

{# Bronze holds as many rows per file as Python's csv module counts records, apart from DuckDB's reader. #}
{% test rows_match_the_records(model, table) %}
with counted as (
    select key, records from {{ source('checks', 'record_counts') }} where {{ files_of(table) }}
),
read as (
    select source_file as key, count(*) as rows from {{ model }} group by source_file
)
select coalesce(counted.key, read.key) as key
from counted
full join read on counted.key = read.key
where coalesce(counted.records, 0) <> coalesce(read.rows, 0)
{% endtest %}
