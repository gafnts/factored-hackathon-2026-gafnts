{# Each layer is a schema of its own, and its tables drop the layer's prefix: bronze.customers, not main_bronze.bronze_customers. #}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name is not none else target.schema }}
{%- endmacro %}

{% macro generate_alias_name(custom_alias_name=none, node=none) -%}
    {%- if custom_alias_name -%}
        {{ custom_alias_name }}
    {%- elif node.config.schema and node.name.startswith(node.config.schema ~ '_') -%}
        {{ node.name[node.config.schema | length + 1:] }}
    {%- else -%}
        {{ node.name }}
    {%- endif -%}
{%- endmacro %}
