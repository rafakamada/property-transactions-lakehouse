with slugified as (
    select
        {{ select_slugified_columns(
            source('raw', 'ipca'),
            fallback_columns=var('ipca_raw_columns')
        ) }}
    from {{ source('raw', 'ipca') }}
)

select
    -- Source Date is MM/YYYY; normalize to first day of that month.
    make_date(
        try_cast(split_part("date", '/', 2) as integer),
        try_cast(split_part("date", '/', 1) as integer),
        1
    ) as "date",
    try_cast(ipca_rate_last_12_months as double) as ipca_rate_last_12_months,
    _source_file,
    _loaded_at
from slugified
