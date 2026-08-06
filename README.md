# property-transactions-lakehouse

Learn DuckDB and dbt while analyzing property transaction data.

Pipeline: yearly landing XLSX (sheets = months) → DuckDB `raw` (full replace) → dbt staging → intermediate → marts.

Modeling and incremental decisions: [docs/modeling.md](docs/modeling.md).  
Progress log: [ITERATION_LOG.md](ITERATION_LOG.md).

## Setup

```bash
uv sync
source .venv/bin/activate
cp .env.example .env   # sets DBT_PROFILES_DIR=.
```

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

## Ingest XLSX into raw

Expected landing layout: **one file per year**, **one sheet per month**. Re-drop a year file when that year is updated or corrected; ingest replaces the corresponding `raw` table.

1. Drop `.xlsx` / `.xlsm` files into `data/landing/`.
2. Run:

```bash
uv run python scripts/ingest_raw.py
```

Tables land in DuckDB schema `raw` inside `data/dev.duckdb`, with source columns preserved plus `_source_file` and `_loaded_at`. Declare each table in `models/staging/_sources.yml` when you start modeling it.

## dbt

```bash
export DBT_PROFILES_DIR=.
dbt debug
dbt run
dbt test
```

- Staging / intermediate: **views** (not incremental).
- Dimension marts: **tables**.
- Fact marts (`fct_*`): **incremental + merge** with a `unique_key` — see [docs/modeling.md](docs/modeling.md).
- After changing incremental model logic: `dbt run -s fct_... --full-refresh`.

## Formatting

```bash
uv run ruff format .
uv run ruff check --fix .
```

## Python tests

```bash
uv run pytest
```

## CI

Pull requests and pushes to `master` run Ruff (check + format) and pytest via GitHub Actions (`.github/workflows/ci.yml`).

When dbt models and transforms are added, extend CI to run fixture ingest plus `dbt run` / `dbt test` — that job is not implemented yet.
