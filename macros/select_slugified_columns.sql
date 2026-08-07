{# Emit a SELECT list that renames relation columns via slugify_identifier.
   Ingest metadata columns matching ^_[a-z0-9_]+$ are left unchanged.
   Business columns are trimmed; empty strings become null.

   During parse (`execute` is false) get_columns_in_relation is empty — emit a
   placeholder so the model still parses; real SQL is built at compile/run. #}
{% macro select_slugified_columns(relation, apply_trim=true) %}
  {%- if not execute -%}
    *
  {%- else -%}
    {%- set columns = adapter.get_columns_in_relation(relation) -%}
    {%- if columns | length == 0 -%}
      {{ exceptions.raise_compiler_error(
        'select_slugified_columns: no columns found on ' ~ relation
      ) }}
    {%- endif -%}
    {%- for col in columns -%}
      {%- set raw_name = col.name -%}
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
  {%- endif -%}
{% endmacro %}
