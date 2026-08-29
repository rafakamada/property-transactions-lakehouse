# Modelagem e materialização

English: [modeling.md](modeling.md)

## Formato da fonte

### ITBI (transações)

Downloads públicos de transações ITBI: [Prefeitura de São Paulo — Dados das Transações Imobiliárias](https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501).

- Um arquivo XLSX por **ano** em `data/landing/` como `YYYY.xlsx`
- O layout das abas é declarado em [`config/ingest_landing.yml`](../config/ingest_landing.yml):
  - **Abas de mês** (`MON-YYYY`) → `UNION ALL` em `raw.itbi_YYYY`
  - **Outras abas declaradas** → uma tabela `raw` cada (`sanitize(sheet)_YYYY` ou `table:` explícito)
- Abas não declaradas falham na ingestão; não há lista de exclusão
- O arquivo do ano corrente é substituído mensalmente; anos anteriores podem ser recolocados quando corrigidos
- A ingestão carrega o raw com **substituição completa** por arquivo (`CREATE OR REPLACE`); raw nunca é um modelo incremental do dbt
- Células das abas de mês são lidas como VARCHAR (`all_varchar`); a tipagem ocorre no staging

### CEP Aberto (referência de endereço)

Dump de CEP baixado de [CEP Aberto](https://www.cepaberto.com/) (partes do estado de São Paulo em `data/landing/cep_aberto/`).

- Partes CSV sem cabeçalho (`sp.cepaberto_parte_*.csv`) são declaradas em `csv_datasets` em [`config/ingest_landing.yml`](../config/ingest_landing.yml) e unidas em `raw.cep_aberto`
- Colunas na ingestão: `cep`, `logradouro`, `complemento`, `bairro`, `id_cidade`, `id_bairro`
- **Por quê:** a coluna `bairro` do ITBI é bagunçada e pouco confiável. O CEP Aberto será juntado pelo `cep` normalizado nas camadas seguintes (intermediate/marts) para corrigir ou enriquecer o bairro. O staging só prepara as chaves de CEP (`stg_cep_aberto` / `stg_itbi`).

### Por que não `dbt seed`

ITBI e CEP Aberto **não** são carregados com [`dbt seed`](https://docs.getdbt.com/reference/commands/seed). Seeds servem para CSVs pequenos e versionados em `seeds/`. Estas fontes são grandes (XLSX de vários MB; ~300k linhas de CEP), ficam em `data/landing/` (gitignored) e precisam de um contrato YAML de ingestão (uniões de abas, colunas de CSV sem cabeçalho, metadados). O caminho é landing → `scripts/ingest_raw.py` → `raw` → `source('raw', ...)`.

`seed-paths: [seeds]` permanece em `dbt_project.yml` para futuras tabelas de referência pequenas, se necessário. O CI também não executa `dbt seed`; linhas sintéticas em `raw` são criadas por [`scripts/seed_ci_raw.py`](../scripts/seed_ci_raw.py), porque os arquivos de landing não estão no git.

## Materializações por camada

| Camada | Padrão | Notas |
|--------|--------|--------|
| Raw (ingestão) | tabela DuckDB | Substituição completa a partir de XLSX / CSV via contrato YAML |
| Staging (`stg_*`) | view | Sempre reflete o raw mais recente; **não** use incremental |
| Intermediate (`int_*`) | view | Promova a table só se o modelo ficar lento |
| Dimensões (`dim_*`) | table | Rebuild completo é aceitável para aprendizado |
| Fatos (`fct_*`) | **incremental + merge** | Foco de aprendizado; veja abaixo |

Os padrões das pastas staging / intermediate / marts estão em `dbt_project.yml`. Modelos de fato sobrescrevem para incremental no próprio `config()`.

## Staging (`stg_itbi`)

- Renomeação mecânica snake_case dos cabeçalhos em português (acentos removidos; stop words `de` / `da` / `do` / `das` / `dos` descartadas)
- Coerção de tipos a partir do VARCHAR da ingestão (datas, numéricos) e trim / string vazia → null
- Limpeza de identificadores e códigos: expandir SQL em notação científica; remover sufixos float do Excel em `uso_iptu` / `padrao_iptu`; CEP com 8 dígitos e zero à esquerda; `proporcao_transmitida` fora de `[0, 100]` vira null
- Remover linhas de lixo que ecoam cabeçalhos (rótulos de coluna em português vazados nas células)
- `UNION ALL` de `raw.itbi_YYYY` para os anos em `vars.itbi_years` ([`dbt_project.yml`](../dbt_project.yml))
- Paridade de colunas entre anos é exigida antes do union (macro em compile-time + teste singular no `dbt test`)
- Verifique com `DBT_PROFILES_DIR=. dbt run -s stg_itbi` e `dbt test`

## Staging (`stg_cep_aberto`)

- View sobre `raw.cep_aberto`; grain de uma linha por CEP
- Mesma normalização de CEP com 8 dígitos e zero à esquerda que `stg_itbi`, para joins em `cep`
- Trim / string vazia → null nos textos; cast de `id_cidade` / `id_bairro` para integer
- Verifique com `DBT_PROFILES_DIR=. dbt run -s stg_cep_aberto` e `dbt test -s stg_cep_aberto`

## Fatos incrementais (decisão de aprendizado)

Use modelos incrementais nos **marts de fato**, não no staging.

Padrão:

```sql
{{ config(
    materialized='incremental',
    unique_key='transaction_id',  -- substitua pela(s) chave(s) de grain reais
    incremental_strategy='merge'
) }}

select ...
from {{ ref('stg_...') }}

{% if is_incremental() %}
  -- prune opcional; o merge em unique_key ainda aplica correções
  where transaction_date >= (
    select coalesce(max(transaction_date), '1900-01-01') from {{ this }}
  )
{% endif %}
```

Requisitos:

- Defina um **grain** estável e `unique_key` (coluna única ou lista)
- Prefira **`merge`** para que correções reingeridas atualizem linhas existentes
- Evite incremental só-append sem chave única — correções tardias seriam perdidas

### Fluxo de rebuild

| Evento | Passos |
|--------|--------|
| Novo mês / arquivo do ano atualizado | Reingerir esse arquivo → `dbt run -s fct_...` |
| Correção em um ano passado | Reingerir esse ano → `dbt run` incremental (merge) |
| Mudança de SQL ou schema do modelo | `dbt run -s fct_... --full-refresh` |

### Progressão de aprendizado

1. Entregue `stg_` (view) + um mart em table; testes verdes  
2. Troque o fato para `incremental` + `unique_key` + `merge`  
3. Rode duas vezes (a segunda deve fazer pouco/nenhum merge se os dados não mudaram)  
4. Altere uma linha no raw, reingerir, rode de novo — confirme que o merge atualiza  
5. Pratique `--full-refresh` após mudanças de lógica  

Não torne todo modelo incremental. Um mart de fato basta para aprender o padrão.
