# Iteration log

Português: [ITERATION_LOG.pt-BR.md](ITERATION_LOG.pt-BR.md)

Newest day first. One section per calendar day. Draft bullets for both this file and
`ITERATION_LOG.pt-BR.md`, preview them to the user, then append under today’s heading
only after confirmation (create the day at the top if missing). See `.cursor/rules/commit-hygiene.mdc`.

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
