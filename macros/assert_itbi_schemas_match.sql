{# Compile-time guard: all raw.itbi_YYYY tables share the same ordered columns.
   Wrapped in `execute` so parse-time (no DB) does not false-fail. #}
{% macro assert_itbi_schemas_match() %}
  {%- if execute -%}
    {%- set years = var('itbi_years') -%}
    {%- if years | length < 1 -%}
      {{ exceptions.raise_compiler_error('vars.itbi_years must not be empty') }}
    {%- endif -%}
    {%- set base_year = years[0] -%}
    {%- set base_rel = source('raw', 'itbi_' ~ base_year) -%}
    {%- set base_cols = adapter.get_columns_in_relation(base_rel) | map(attribute='name') | list -%}
    {%- if base_cols | length == 0 -%}
      {{ exceptions.raise_compiler_error(
        'assert_itbi_schemas_match: raw.itbi_' ~ base_year ~ ' has no columns (ingest first?)'
      ) }}
    {%- endif -%}
    {%- for year in years -%}
      {%- if year != base_year -%}
        {%- set rel = source('raw', 'itbi_' ~ year) -%}
        {%- set cols = adapter.get_columns_in_relation(rel) | map(attribute='name') | list -%}
        {%- if cols != base_cols -%}
          {{ exceptions.raise_compiler_error(
            'raw.itbi_' ~ year ~ ' columns do not match raw.itbi_' ~ base_year
            ~ '.\nexpected (' ~ base_cols | length ~ '): ' ~ (base_cols | join(', '))
            ~ '\nactual (' ~ cols | length ~ '): ' ~ (cols | join(', '))
          ) }}
        {%- endif -%}
      {%- endif -%}
    {%- endfor -%}
  {%- endif -%}
{% endmacro %}
