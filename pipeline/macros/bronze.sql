{# A bronze table: every row of the source's files, typed by its contract, with the file it came from and the snapshot. #}

{% macro bronze(table) %}
select
    * exclude (filename),
    replace(filename, '{{ var("snapshot_root") }}/', '') as source_file,
    '{{ var("snapshot_id") }}' as snapshot_id
from {{ source('snapshot', table) }}
{% endmacro %}

{% macro partition_date(key) -%}
    strptime(regexp_extract({{ key }}, '_(\d{8})\.csv$', 1), '%Y%m%d')::date
{%- endmacro %}

{% macro files_of(table) -%}
    (key = '{{ table }}.csv' or key like '{{ table }}/%')
{%- endmacro %}
