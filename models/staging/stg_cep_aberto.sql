select
    lpad(
        cast(cast(try_cast(cep as double) as bigint) as varchar),
        8,
        '0'
    ) as cep,
    nullif(trim(logradouro), '') as logradouro,
    nullif(trim(complemento), '') as complemento,
    nullif(trim(bairro), '') as bairro,
    try_cast(id_cidade as integer) as id_cidade,
    try_cast(id_bairro as integer) as id_bairro,
    _source_file,
    _loaded_at
from {{ source('raw', 'cep_aberto') }}
