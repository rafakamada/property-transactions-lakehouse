# Iteration log

Português: [ITERATION_LOG.pt-BR.md](ITERATION_LOG.pt-BR.md)

Newest day first. One section per calendar day. Draft bullets for both this file and
`ITERATION_LOG.pt-BR.md`, preview them to the user, then append under today’s heading
only after confirmation (create the day at the top if missing). See `.cursor/rules/commit-hygiene.mdc`.

## 2026-08-29

- **Add CEP Aberto to raw and staging** — extend ingest with `csv_datasets` for SP CEP dumps → `raw.cep_aberto`; add `stg_cep_aberto` with ITBI-matching CEP padding and grain tests; CI seed + docs note [cepaberto.com](https://www.cepaberto.com/) and messy ITBI `bairro` enrichment via CEP. Verify: `uv run pytest`, `uv run python scripts/ingest_raw.py`, `DBT_PROFILES_DIR=. dbt run -s stg_cep_aberto`, `dbt test -s stg_cep_aberto`
- **Enforce stg_itbi identifier types** — cast `n_cadastro_sql`/`uso_iptu` to varchar, `numero`/`matricula_imovel` to integer, and normalize CEP to an 8-digit zero-padded string; document CEP in `schema.yml`; ignore local `analyses/*` scratch SQL.
- **Add native dbt unit tests for casts** — fixture SQL under `tests/fixtures/` plus `test_stg_itbi_cast_fixtures` / `test_stg_itbi_cep_invalid_becomes_null`; pin `dbt-core>=1.12.3`. Verify: `DBT_PROFILES_DIR=. dbt test --select "test_type:unit"`
- **Harden stg_itbi casts and junk filters** — expand scientific-notation SQL; strip Excel float suffixes on `uso_iptu`/`padrao_iptu`; null `proporcao_transmitida` outside `[0, 100]`; drop header-echo rows; extend unit-test fixtures. Verify: `DBT_PROFILES_DIR=. dbt test --select "test_type:unit"`, `dbt run -s stg_itbi`, `dbt test`

## 2026-08-07

- **Add ITBI staging layer** — `stg_itbi` unions `raw.itbi_YYYY` with Jinja slugify (stop words dropped), type coercion, and schema-match guards; `schema.yml` + singular tests; docs and `configure-itbi-landing` updated for `vars.itbi_years`. Verify: `DBT_PROFILES_DIR=. dbt run -s stg_itbi`, `dbt test`
- **Add dbt to CI** — seed synthetic `raw.itbi_YYYY` via `scripts/seed_ci_raw.py`, then `dbt run -s stg_itbi` and `dbt test` in GitHub Actions; README CI notes updated

## 2026-08-06

- **Add pt-BR docs and condense iteration log** — README TOC; `README.pt-BR.md`, `docs/modeling.pt-BR.md`, and `ITERATION_LOG.pt-BR.md`; one section per day in both logs; commit hygiene previews EN/pt-BR bullets and waits for confirmation before committing
- **Document querying DuckDB** — README: how to list/query `raw` tables via Python, DuckDB CLI, DBeaver, and Cursor/VS Code
- **Add raw ingestion** — config-driven multi-sheet ITBI ingest (`config/ingest_landing.yml` → `raw.itbi_YYYY` + year-suffixed other sheets); project skill `configure-itbi-landing`; docs cite Prefeitura portal. Verify: `uv run pytest`, `uv run python scripts/ingest_raw.py`
- **Fix CI push trigger for default branch** — point workflow push trigger and docs at `master` (repo default), not `main`
- **Add CI for lint and unit tests** — GitHub Actions runs Ruff and pytest on PRs and pushes; README notes dbt ingest/run/test CI should follow once transforms exist. Verify: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`

## 2026-08-03

- **Bootstrap project tooling** — uv + Python 3.12, dbt-duckdb, DuckDB, Ruff, pytest; landing XLSX → raw ingest script; dbt staging/intermediate/marts scaffold; Cursor rules for modeling, data-TDD, and commit hygiene
- **Incremental facts learning decision** — document source shape (yearly XLSX, monthly sheets, raw full-replace); keep stg/int as views, dim as tables; learn incremental **merge** on `fct_*` only; added `docs/modeling.md`
- **Fail on ingest table-name collisions** — raise when distinct landing files sanitize to the same `raw` table name; cover hyphen/underscore and case/space collisions in unit tests. Verify: `uv run pytest tests/unit/test_ingest_raw.py`
