---
name: configure-itbi-landing
description: >-
  Configure ITBI landing XLSX ingest — copy/rename yearly files, update
  config/ingest_landing.yml (month union + other year-suffixed tables), register
  dbt sources, run ingest. Use when adding or updating Prefeitura ITBI
  spreadsheets, landing Excel, ingest YAML, or raw ITBI tables.
---

# Configure ITBI landing ingest

Public data portal: https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501

## When to use

Adding a new year file, replacing a corrected year, or changing sheet layout in `config/ingest_landing.yml`.

## Workflow

1. **Determine year** from month tab names (`MON-YYYY`, e.g. `JAN-2025`). Download names are unreliable.
2. **Copy** into `data/landing/itbi/YYYY.xlsx` (landing is gitignored; do not commit multi‑MB XLSX).
3. **List all sheet names** (zipfile/`xl/workbook.xml` or DuckDB). Every sheet must be either:
   - matched by `month_sheets.pattern`, or
   - listed under `other_sheets` (including LEGENDA, EXPLICAÇÕES, Tabela de USOS, Tabela de PADRÕES).
4. **Update** [`config/ingest_landing.yml`](../../../config/ingest_landing.yml):
   - `files."YYYY.xlsx"` entry (`year`, `transaction_table: itbi_YYYY`) — basename key; file lives under `data/landing/itbi/`
   - `month_sheets.pattern` for that year; set `overrides` with `header: false` when row 1 is data (probe `A1`)
   - `other_sheets` for every non-month tab; set explicit ASCII `table:` when sanitize would keep accents
5. **Update** [`models/staging/_sources.yml`](../../../models/staging/_sources.yml) for `itbi_YYYY` and each other table.
6. **Append** the year to `vars.itbi_years` in [`dbt_project.yml`](../../../dbt_project.yml) so `stg_itbi` includes it.
7. **Run** `uv run python scripts/ingest_raw.py` and spot-check row counts / columns in DuckDB.
8. **Run** `DBT_PROFILES_DIR=. dbt run -s stg_itbi` and `DBT_PROFILES_DIR=. dbt test` (schema-match fails if the new year’s columns diverge from other years).
9. Keep the portal URL in README current when documenting new years.

## Rules

- Undeclared workbook sheet → ingest fails (no skip list).
- Month sheets → one `raw.itbi_YYYY` via `UNION ALL`.
- Other declared sheets → one table each (`sanitize(sheet)_YYYY` or explicit `table:`).
- Month reads use `all_varchar`, `range: A1:AB`, `stop_at_empty: true` from defaults.
- Other sheets do not use the transaction range unless overridden.
- Changing `defaults.transaction_columns` requires all yearly `raw.itbi_*` tables to stay aligned (staging schema-match + union).

See [reference.md](reference.md) for YAML fields and known quirks.
