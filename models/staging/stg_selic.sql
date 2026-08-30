with slugified as (
    select
        {{ select_slugified_columns(
            source('raw', 'selic'),
            fallback_columns=var('selic_raw_columns')
        ) }}
    from {{ source('raw', 'selic') }}
)

select
    try_cast(numero_reuniao_copom as double) as numero_reuniao_copom,
    try_cast(reuniao_extraordinaria as boolean) as reuniao_extraordinaria,
    try_cast(data_reuniao_copom as timestamptz) as data_reuniao_copom,
    vies,
    try_cast(uso_meta_selic as boolean) as uso_meta_selic,
    try_cast(data_inicio_vigencia as timestamptz) as data_inicio_vigencia,
    try_cast(data_fim_vigencia as timestamptz) as data_fim_vigencia,
    try_cast(meta_selic as double) as meta_selic,
    try_cast(taxa_tban as double) as taxa_tban,
    try_cast(taxa_selic_efetiva_vigencia as double) as taxa_selic_efetiva_vigencia,
    try_cast(taxa_selic_efetiva_anualizada as double)
        as taxa_selic_efetiva_anualizada,
    try_cast(descisao_monocratica_pres as boolean) as descisao_monocratica_pres,
    _source_file,
    _loaded_at
from slugified
