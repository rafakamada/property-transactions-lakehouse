{# Mechanical snake_case: CamelCase split, accents stripped, Portuguese stop
   words dropped. #}
{% macro slugify_identifier(name) %}
  {%- set ns = namespace(s=(name | string)) -%}
  {# Split CamelCase / PascalCase before lowercasing (e.g. MetaSelic → Meta_Selic). #}
  {%- set ns.s = modules.re.sub('([a-z0-9])([A-Z])', '\\1_\\2', ns.s) -%}
  {%- set ns.s = ns.s | lower -%}
  {%- set accent_pairs = [
    ('á', 'a'), ('à', 'a'), ('â', 'a'), ('ã', 'a'), ('ä', 'a'),
    ('é', 'e'), ('è', 'e'), ('ê', 'e'), ('ë', 'e'),
    ('í', 'i'), ('ì', 'i'), ('î', 'i'), ('ï', 'i'),
    ('ó', 'o'), ('ò', 'o'), ('ô', 'o'), ('õ', 'o'), ('ö', 'o'),
    ('ú', 'u'), ('ù', 'u'), ('û', 'u'), ('ü', 'u'),
    ('ç', 'c'), ('ñ', 'n')
  ] -%}
  {%- for old, new in accent_pairs -%}
    {%- set ns.s = ns.s.replace(old, new) -%}
  {%- endfor -%}
  {%- set tokens = modules.re.findall('[a-z0-9]+', ns.s) -%}
  {%- set stop_words = ['de', 'da', 'do', 'das', 'dos'] -%}
  {%- set kept = namespace(tokens=[]) -%}
  {%- for token in tokens -%}
    {%- if token not in stop_words -%}
      {%- set kept.tokens = kept.tokens + [token] -%}
    {%- endif -%}
  {%- endfor -%}
  {{- kept.tokens | join('_') -}}
{% endmacro %}
