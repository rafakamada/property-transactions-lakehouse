# ITBI ingest config reference

## `config/ingest_landing.yml`

| Field | Role |
|-------|------|
| `version` | Must be `1` |
| `defaults.all_varchar` | Force VARCHAR on Excel read |
| `defaults.transaction_range` | Usually `A1:AB` (28 month columns) |
| `defaults.stop_at_empty` | Stop at first empty row for month sheets |
| `defaults.transaction_columns` | Canonical 28 month column names (all yearly `raw.itbi_*` must stay aligned) |
| `files.<name>.year` | Calendar year; unique across files. `<name>` is the basename under `data/landing/itbi/` (e.g. `2024.xlsx`) |
| `files.<name>.transaction_table` | Target for month union (`itbi_YYYY`) |
| `files.<name>.month_sheets.pattern` | Regex for month tabs |
| `files.<name>.month_sheets.header` | Default header flag for months |
| `files.<name>.month_sheets.overrides` | Per-sheet `header` / `range` |
| `files.<name>.other_sheets` | Map sheet name → `{ table?, header?, range? }` |

## Known Excel quirks

- Mixed types in a column break inference without `all_varchar: true`.
- Empty early cells truncate inferred width — force `A1:AB` for months.
- Some months lack a header row (`header: false` → read from `A1`).
- Some months have mislabeled/duplicate headers (e.g. 2024 FEV/MAI/SET, 2026 FEV typo `pardão`). Prefer `header: true` so row 1 is skipped; ingest always applies canonical `transaction_columns` by position (`A2:AB`), so wrong header *names* do not matter.
- Truly headerless months (2024 JAN/OUT) must use `header: false`.

## Portal

https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501
