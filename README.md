# property-transactions-lakehouse

Português: [README.pt-BR.md](README.pt-BR.md)

Learn DuckDB and dbt while analyzing property transaction data.

**Public data source:** [Dados das Transações Imobiliárias com recolhimento de ITBI — Prefeitura de São Paulo](https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501) (yearly Excel/ODS downloads).

Pipeline: yearly landing XLSX (sheets = months + reference tabs) → DuckDB `raw` (full replace, config-driven) → dbt staging → intermediate → marts.

Modeling and incremental decisions: [docs/modeling.md](docs/modeling.md).  
Ingest contract: [config/ingest_landing.yml](config/ingest_landing.yml).  
Progress log: [ITERATION_LOG.md](ITERATION_LOG.md) ([pt-BR](ITERATION_LOG.pt-BR.md)).

## Contents

- [Setup](#setup)
- [Ingest XLSX into raw](#ingest-xlsx-into-raw)
- [Query DuckDB](#query-duckdb)
- [dbt](#dbt)
- [Formatting](#formatting)
- [Python tests](#python-tests)
- [CI](#ci)

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

> **Tip:**  
> When adding or updating a year spreadsheet, you can use the project skill  
> **configure-itbi-landing** (`.cursor/skills/configure-itbi-landing/`) to walk through file copy/rename, YAML config, `_sources.yml` registration, and ingest steps.  
> This is optional but can help automate and simplify the workflow.

## Query DuckDB

Local database file: [`data/dev.duckdb`](data/dev.duckdb). Ingested tables live in schema **`raw`** (for example `raw.itbi_2026`).

DuckDB allows one writer at a time. Close GUI connections before running ingest, and prefer read-only when only exploring.

### Python (via uv)

```bash
uv run python -c "
import duckdb
con = duckdb.connect('data/dev.duckdb', read_only=True)
con.sql('SHOW TABLES FROM raw').show()
con.sql('SELECT count(*) FROM raw.itbi_2026').show()
"
```

Interactive:

```bash
uv run python
```

```python
import duckdb

con = duckdb.connect("data/dev.duckdb", read_only=True)
con.sql("SHOW TABLES FROM raw")
con.sql("SELECT * FROM raw.itbi_2026 LIMIT 5")
```

### DuckDB CLI

If the [`duckdb`](https://duckdb.org/docs/stable/clients/cli) binary is installed:

```bash
duckdb data/dev.duckdb -readonly
```

Then:

```sql
SHOW TABLES FROM raw;
SELECT _reference_month, count(*) FROM raw.itbi_2026 GROUP BY 1 ORDER BY 1;
```

### DBeaver

1. New connection → **DuckDB**.
2. Path: absolute path to `data/dev.duckdb` in this repo.
3. Browse schema `raw` and run SQL.

### Cursor / VS Code

Install a DuckDB-capable database extension (for example SQLTools with a DuckDB driver, or another “Database Client” that lists DuckDB). Create a connection pointed at `data/dev.duckdb`, then query schema `raw`.

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

Pull requests and pushes to `master` run Ruff (check + format), pytest, then a
minimal DuckDB raw seed (`scripts/seed_ci_raw.py`) plus `dbt run -s stg_itbi` and
`dbt test` via GitHub Actions (`.github/workflows/ci.yml`). Landing XLSX files are
not in git; CI seeds synthetic `raw.itbi_YYYY` rows instead of full ingest.
