{{ config(materialized='view') }}

{# Fail compile if yearly raw.itbi_* schemas diverge before UNION ALL. #}
{{ assert_itbi_schemas_match() }}

with
{% for year in var('itbi_years') %}
year_{{ year }} as (
    select
        {{ select_slugified_columns(source('raw', 'itbi_' ~ year)) }},
        {{ year }} as source_year
    from {{ source('raw', 'itbi_' ~ year) }}
){% if not loop.last %},{% endif %}
{% endfor %}

, unioned as (
    {% for year in var('itbi_years') %}
    select * from year_{{ year }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    -- Excel may store large SQLs as scientific notation (e.g. 2.6015E9). Expand
    -- those via double→bigint; leave other strings alone to preserve leading zeros.
    case
        when upper(n_cadastro_sql) like '%E%'
            then cast(cast(try_cast(n_cadastro_sql as double) as bigint) as varchar)
        else cast(n_cadastro_sql as varchar)
    end as n_cadastro_sql,
    nome_logradouro,
    try_cast(numero as integer) as numero,
    complemento,
    bairro,
    referencia,
    lpad(
        cast(cast(try_cast(cep as double) as bigint) as varchar),
        8,
        '0'
    ) as cep,
    natureza_transacao,
    try_cast(valor_transacao_declarado_pelo_contribuinte as double)
        as valor_transacao_declarado_pelo_contribuinte,
    coalesce(
        try_cast(data_transacao as date),
        date '1899-12-30' + try_cast(data_transacao as integer)
    ) as data_transacao,
    try_cast(valor_venal_referencia as double) as valor_venal_referencia,
    case
        when try_cast(proporcao_transmitida as double) between 0 and 100
            then try_cast(proporcao_transmitida as double)
        else null
    end as proporcao_transmitida,
    try_cast(valor_venal_referencia_proporcional as double)
        as valor_venal_referencia_proporcional,
    try_cast(base_calculo_adotada as double) as base_calculo_adotada,
    tipo_financiamento,
    try_cast(valor_financiado as double) as valor_financiado,
    cartorio_registro,
    try_cast(matricula_imovel as integer) as matricula_imovel,
    situacao_sql,
    try_cast(area_terreno_m2 as double) as area_terreno_m2,
    try_cast(testada_m as double) as testada_m,
    try_cast(fracao_ideal as double) as fracao_ideal,
    try_cast(area_construida_m2 as double) as area_construida_m2,
    cast(cast(try_cast(uso_iptu as double) as bigint) as varchar) as uso_iptu,
    descricao_uso_iptu,
    cast(cast(try_cast(padrao_iptu as double) as bigint) as varchar) as padrao_iptu,
    descricao_padrao_iptu,
    acc_iptu,
    _source_file,
    _source_sheet,
    _loaded_at,
    try_cast(_reference_month as date) as _reference_month,
    source_year
from unioned
-- Drop rows that echo Portuguese column headers into data cells.
where coalesce(natureza_transacao, '') <> 'Natureza de Transação'
  and coalesce(situacao_sql, '') <> 'Situação do SQL'
  and coalesce(tipo_financiamento, '') <> 'Tipo de Financiamento'
