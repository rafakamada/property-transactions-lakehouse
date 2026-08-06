# property-transactions-lakehouse

Learn DuckDB and dbt while analyzing property transaction data.

**Public data source:** [Dados das Transações Imobiliárias com recolhimento de ITBI — Prefeitura de São Paulo](https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501) (yearly Excel/ODS downloads).

Pipeline: yearly landing XLSX (sheets = months + reference tabs) → DuckDB `raw` (full replace, config-driven) → dbt staging → intermediate → marts.

Modeling and incremental decisions: [docs/modeling.md](docs/modeling.md).  
Ingest contract: [config/ingest_landing.yml](config/ingest_landing.yml).  
Progress log: [ITERATION_LOG.md](ITERATION_LOG.md).

## Setup

```bash
uv sync
source .venv/bin/activate
cp .env.example .env   # sets DBT_PROFILES_DIR=.
```

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

## Ingest XLSX into raw

1. Download a year file from the [Prefeitura portal](https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501).
2. Rename/copy into `data/landing/YYYY.xlsx` (download filenames are unreliable).
3. Declare sheets in [config/ingest_landing.yml](config/ingest_landing.yml):
   - **Month sheets** (`MON-YYYY`) → unioned into `raw.itbi_YYYY`
   - **Other sheets** (LEGENDA, EXPLICAÇÕES, usos, padrões, …) → one table each with a year suffix
4. Register new tables in `models/staging/_sources.yml`.
5. Run:

```bash
uv run python scripts/ingest_raw.py
```

Re-drop a year file when that year is updated or corrected; ingest replaces the corresponding `raw` tables for that file.

Optional: when adding or updating a year spreadsheet, the project skill **configure-itbi-landing** (`.cursor/skills/configure-itbi-landing/`) walks through copy/rename, YAML, `_sources.yml`, and ingest — not mandatory, but it avoids doing that work by hand.

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
