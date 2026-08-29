{# Emit a SELECT list that renames columns via slugify_identifier.
   Ingest metadata columns matching ^_[a-z0-9_]+$ are left unchanged.
   Business columns are trimmed; empty strings become null.

   During parse (`execute` is false) get_columns_in_relation is empty — emit a
   placeholder so the model still parses; real SQL is built at compile/run.

   When the relation is a unit-test CTE (dbt-core), introspection is also empty.
   Pass fallback_columns (e.g. var('itbi_raw_columns')) so slugify still runs. #}
{% macro select_slugified_column_list(column_names, apply_trim=true) %}
  {%- for raw_name in column_names -%}
    {%- if modules.re.match('^_[a-z0-9_]+$', raw_name) -%}
      {{ adapter.quote(raw_name) }}
    {%- else -%}
      {%- set alias = slugify_identifier(raw_name) -%}
      {%- if apply_trim -%}
        nullif(trim(cast({{ adapter.quote(raw_name) }} as varchar)), '') as {{ alias }}
      {%- else -%}
        {{ adapter.quote(raw_name) }} as {{ alias }}
      {%- endif -%}
    {%- endif -%}
    {%- if not loop.last -%}, {% endif -%}
  {%- endfor -%}
{% endmacro %}

{% macro select_slugified_columns(relation, apply_trim=true, fallback_columns=none) %}
  {%- if not execute -%}
    *
  {%- else -%}
    {%- set columns = adapter.get_columns_in_relation(relation) -%}
    {%- if columns | length > 0 -%}
      {{ select_slugified_column_list(columns | map(attribute='name') | list, apply_trim) }}
    {%- elif fallback_columns is not none and (fallback_columns | length > 0) -%}
      {{ select_slugified_column_list(fallback_columns, apply_trim) }}
    {%- else -%}
      {{ exceptions.raise_compiler_error(
        'select_slugified_columns: no columns found on ' ~ relation
        ~ ' (pass fallback_columns for unit-test CTEs)'
      ) }}
    {%- endif -%}
  {%- endif -%}
{% endmacro %}
