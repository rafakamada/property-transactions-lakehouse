# Modeling and materialization

## Source shape

- One XLSX file per **year** in `data/landing/`
- One sheet per **month** inside each file
- Current-year file is replaced monthly; past years may be re-dropped when corrected
- Ingest loads raw with **full replace** per file (`CREATE OR REPLACE`); raw is never a dbt incremental model
- Multi-sheet (one tab per month) loading is part of the intended ingest design; extend `scripts/ingest_raw.py` when real year files are added

## Layer materializations

| Layer | Default | Notes |
|-------|---------|--------|
| Raw (ingest) | DuckDB table | Year-level replace from XLSX |
| Staging (`stg_*`) | view | Always reflect latest raw; do **not** use incremental |
| Intermediate (`int_*`) | view | Promote to table only if a model is slow |
| Dimensions (`dim_*`) | table | Full rebuild is fine for learning |
| Facts (`fct_*`) | **incremental + merge** | Learning focus; see below |

Defaults for staging / intermediate / marts folders are in `dbt_project.yml`. Fact models override to incremental in their own `config()`.

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
