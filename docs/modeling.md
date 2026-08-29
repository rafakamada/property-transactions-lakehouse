# Modeling and materialization

Português: [modeling.pt-BR.md](modeling.pt-BR.md)

## Source shape

### ITBI (transactions)

Public ITBI transaction downloads: [Prefeitura de São Paulo — Dados das Transações Imobiliárias](https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501).

- One XLSX file per **year** in `data/landing/` as `YYYY.xlsx`
- Sheet layout is declared in [`config/ingest_landing.yml`](../config/ingest_landing.yml):
  - **Month sheets** (`MON-YYYY`) → `UNION ALL` into `raw.itbi_YYYY`
  - **Other declared sheets** → one `raw` table each (`sanitize(sheet)_YYYY` or explicit `table:`)
- Undeclared sheets fail ingest; there is no skip list
- Current-year file is replaced monthly; past years may be re-dropped when corrected
- Ingest loads raw with **full replace** per file (`CREATE OR REPLACE`); raw is never a dbt incremental model
- Month cells are read as VARCHAR (`all_varchar`) so typing happens in staging

### CEP Aberto (address reference)

CEP dump downloaded from [CEP Aberto](https://www.cepaberto.com/) (São Paulo state parts under `data/landing/cep_aberto/`).

- Headerless CSV parts (`sp.cepaberto_parte_*.csv`) are declared under `csv_datasets` in [`config/ingest_landing.yml`](../config/ingest_landing.yml) and unioned into `raw.cep_aberto`
- Columns at ingest: `cep`, `logradouro`, `complemento`, `bairro`, `id_cidade`, `id_bairro`
- **Why:** ITBI’s `bairro` (neighborhood) column is messy and unreliable. CEP Aberto will be joined on normalized `cep` downstream (intermediate/marts) to fix or enrich neighborhood values. Staging only prepares matching CEP keys (`stg_cep_aberto` / `stg_itbi`).

### Why not `dbt seed`

ITBI and CEP Aberto are **not** loaded with [`dbt seed`](https://docs.getdbt.com/reference/commands/seed). Seeds are for small, version-controlled CSVs checked into `seeds/`. These sources are large (multi‑MB XLSX; ~300k CEP rows), live under gitignored `data/landing/`, and need a YAML ingest contract (sheet unions, headerless CSV columns, metadata). Landing → `scripts/ingest_raw.py` → `raw` → `source('raw', ...)` is the path.

`seed-paths: [seeds]` remains in `dbt_project.yml` for future tiny reference tables if needed. CI does not run `dbt seed` either; synthetic `raw` rows are created by [`scripts/seed_ci_raw.py`](../scripts/seed_ci_raw.py) because landing files are not in git.

## Layer materializations

| Layer | Default | Notes |
|-------|---------|--------|
| Raw (ingest) | DuckDB table | Full replace from landing XLSX / CSV via YAML contract |
| Staging (`stg_*`) | view | Always reflect latest raw; do **not** use incremental |
| Intermediate (`int_*`) | view | Promote to table only if a model is slow |
| Dimensions (`dim_*`) | table | Full rebuild is fine for learning |
| Facts (`fct_*`) | **incremental + merge** | Learning focus; see below |

Defaults for staging / intermediate / marts folders are in `dbt_project.yml`. Fact models override to incremental in their own `config()`.

## Staging (`stg_itbi`)

- Mechanical snake_case rename of Portuguese headers (accents stripped; stop words `de` / `da` / `do` / `das` / `dos` dropped)
- Type coercion from ingest VARCHAR (dates, numerics) plus trim / empty-string → null
- Identifier and code cleanup: expand scientific-notation SQL; strip Excel float suffixes on `uso_iptu` / `padrao_iptu`; 8-digit zero-padded CEP; null `proporcao_transmitida` outside `[0, 100]`
- Drop header-echo junk rows (Portuguese column labels leaked into data cells)
- `UNION ALL` of `raw.itbi_YYYY` for years in `vars.itbi_years` ([`dbt_project.yml`](../dbt_project.yml))
- Yearly column parity is enforced before union (compile-time macro + singular `dbt test`)
- Verify with `DBT_PROFILES_DIR=. dbt run -s stg_itbi` and `dbt test`

## Staging (`stg_cep_aberto`)

- View over `raw.cep_aberto`; grain is one row per CEP
- Same 8-digit zero-padded CEP normalization as `stg_itbi` so joins on `cep` match
- Trim / empty-string → null on text fields; cast `id_cidade` / `id_bairro` to integer
- Verify with `DBT_PROFILES_DIR=. dbt run -s stg_cep_aberto` and `dbt test -s stg_cep_aberto`

## Incremental facts (learning decision)

Use incremental models on **fact marts**, not on staging.

Pattern:

```sql
{{ config(
    materialized='incremental',
    unique_key='transaction_id',  -- replace with real grain key(s)
    incremental_strategy='merge'
) }}

select ...
from {{ ref('stg_...') }}

{% if is_incremental() %}
  -- optional prune; merge on unique_key still applies corrections
  where transaction_date >= (
    select coalesce(max(transaction_date), '1900-01-01') from {{ this }}
  )
{% endif %}
```

Requirements:

- Define a stable **grain** and `unique_key` (single column or list)
- Prefer **`merge`** so re-ingested corrections update existing rows
- Avoid append-only incremental without a unique key — late corrections would be missed

### Rebuild workflow

| Event | Steps |
|-------|--------|
| New month / updated year file | Re-ingest that file → `dbt run -s fct_...` |
| Correction in a past year | Re-ingest that year → incremental `dbt run` (merge) |
| Model SQL or schema change | `dbt run -s fct_... --full-refresh` |

### Learning progression

1. Ship `stg_` (view) + a table mart; tests green  
2. Switch the fact to `incremental` + `unique_key` + `merge`  
3. Run twice (second run should merge little/nothing if data unchanged)  
4. Change a raw row, re-ingest, run again — confirm merge updates  
5. Practice `--full-refresh` after logic changes  

Do not make every model incremental. One fact mart is enough to learn the pattern.
