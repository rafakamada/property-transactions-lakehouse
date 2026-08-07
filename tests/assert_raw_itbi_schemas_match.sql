-- Singular test: all vars.itbi_years raw.itbi_* tables share the same ordered columns.
with base as (
    select list(column_name order by ordinal_position) as cols
    from information_schema.columns
    where table_schema = 'raw'
      and table_name = 'itbi_{{ var("itbi_years")[0] }}'
),

per_year as (
    {% for year in var('itbi_years') %}
    select
        {{ year }} as year,
        list(column_name order by ordinal_position) as cols
    from information_schema.columns
    where table_schema = 'raw'
      and table_name = 'itbi_{{ year }}'
    {% if not loop.last %}
    union all
    {% endif %}
    {% endfor %}
)

select
    p.year,
    p.cols as actual_cols,
    b.cols as expected_cols
from per_year as p
cross join base as b
where p.cols is distinct from b.cols
