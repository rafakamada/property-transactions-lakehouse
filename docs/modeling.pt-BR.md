# Modelagem e materialização

English: [modeling.md](modeling.md)

## Formato da fonte

Downloads públicos de transações ITBI: [Prefeitura de São Paulo — Dados das Transações Imobiliárias](https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501).

- Um arquivo XLSX por **ano** em `data/landing/` como `YYYY.xlsx`
- O layout das abas é declarado em [`config/ingest_landing.yml`](../config/ingest_landing.yml):
  - **Abas de mês** (`MON-YYYY`) → `UNION ALL` em `raw.itbi_YYYY`
  - **Outras abas declaradas** → uma tabela `raw` cada (`sanitize(sheet)_YYYY` ou `table:` explícito)
- Abas não declaradas falham na ingestão; não há lista de exclusão
- O arquivo do ano corrente é substituído mensalmente; anos anteriores podem ser recolocados quando corrigidos
- A ingestão carrega o raw com **substituição completa** por arquivo (`CREATE OR REPLACE`); raw nunca é um modelo incremental do dbt
- Células das abas de mês são lidas como VARCHAR (`all_varchar`); a tipagem ocorre no staging

## Materializações por camada

| Camada | Padrão | Notas |
|--------|--------|--------|
| Raw (ingestão) | tabela DuckDB | Substituição no nível do ano a partir do XLSX via contrato YAML |
| Staging (`stg_*`) | view | Sempre reflete o raw mais recente; **não** use incremental |
| Intermediate (`int_*`) | view | Promova a table só se o modelo ficar lento |
| Dimensões (`dim_*`) | table | Rebuild completo é aceitável para aprendizado |
| Fatos (`fct_*`) | **incremental + merge** | Foco de aprendizado; veja abaixo |

Os padrões das pastas staging / intermediate / marts estão em `dbt_project.yml`. Modelos de fato sobrescrevem para incremental no próprio `config()`.

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
