{# One spelling per country (ADR-0006): Mexican charges are spelled both ways, and the spelling decides whether a charge reads as abroad. #}
{% macro one_spelling(column) -%}
    case when trim({{ column }}) = 'Mexico' then 'México' else trim({{ column }}) end
{%- endmacro %}

{# Trimmed, and empty once trimmed is missing: record text is never an empty string. #}
{% macro trimmed(column) -%}
    nullif(trim({{ column }}), '')
{%- endmacro %}
