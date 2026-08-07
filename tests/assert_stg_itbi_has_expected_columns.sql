-- Singular test: stg_itbi exposes expected slugified column names (stop words dropped).
with expected(column_name) as (
    values
        ('n_cadastro_sql'),
        ('nome_logradouro'),
        ('numero'),
        ('complemento'),
        ('bairro'),
        ('referencia'),
        ('cep'),
        ('natureza_transacao'),
        ('valor_transacao_declarado_pelo_contribuinte'),
        ('data_transacao'),
        ('valor_venal_referencia'),
        ('proporcao_transmitida'),
        ('valor_venal_referencia_proporcional'),
        ('base_calculo_adotada'),
        ('tipo_financiamento'),
        ('valor_financiado'),
        ('cartorio_registro'),
        ('matricula_imovel'),
        ('situacao_sql'),
        ('area_terreno_m2'),
        ('testada_m'),
        ('fracao_ideal'),
        ('area_construida_m2'),
        ('uso_iptu'),
        ('descricao_uso_iptu'),
        ('padrao_iptu'),
        ('descricao_padrao_iptu'),
        ('acc_iptu'),
        ('_source_file'),
        ('_source_sheet'),
        ('_loaded_at'),
        ('_reference_month'),
        ('source_year')
),

actual as (
    select column_name
    from information_schema.columns
    where table_schema = '{{ target.schema }}'
      and table_name = 'stg_itbi'
)

select e.column_name as missing_column
from expected as e
left join actual as a using (column_name)
where a.column_name is null
