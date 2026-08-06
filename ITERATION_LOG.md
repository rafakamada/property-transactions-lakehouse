# Iteration log

Newest entries first. Update this file as part of every commit (see `.cursor/rules/commit-hygiene.mdc`).

## 2026-08-06 — Add raw ingestion

- Config-driven multi-sheet ITBI ingest (`config/ingest_landing.yml` → `raw.itbi_YYYY` + year-suffixed other sheets)
- Project skill `configure-itbi-landing` for adding/updating year files; docs cite Prefeitura portal
- Verify: `uv run pytest`, `uv run python scripts/ingest_raw.py`

## 2026-08-06 — Fix CI push trigger for default branch

- Point workflow push trigger and docs at `master` (repo default), not `main`

## 2026-08-06 — Add CI for lint and unit tests

- GitHub Actions workflow runs Ruff and pytest on PRs and pushes to `main`
- README notes that dbt ingest/run/test CI should follow once transforms exist
- Verify: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`

## 2026-08-03 — Fail on ingest table-name collisions

- Raise when distinct landing files sanitize to the same `raw` table name
- Cover hyphen/underscore and case/space collisions in unit tests
- Verify: `uv run pytest tests/unit/test_ingest_raw.py`

## 2026-08-03 — Initial setup

- uv + Python 3.12, dbt-duckdb, DuckDB, Ruff, pytest
- Landing XLSX → raw ingest; dbt scaffold; unit tests for ingest helpers
- Incremental `fct_*` learning decision documented in `docs/modeling.md`
- Cursor rules: modeling, data-TDD, commit hygiene

## 2026-08-03 — Incremental facts learning decision

- Documented source shape: yearly XLSX, monthly sheets, raw full-replace on re-ingest
- Keep stg/int as views; dim as tables; learn incremental **merge** on `fct_*` only
- Added `docs/modeling.md`; updated README, `dbt_project.yml` comments, and Cursor rules

## 2026-08-03 — Bootstrap project tooling

- uv + Python 3.12, dbt-duckdb, DuckDB, Ruff
- Landing XLSX → raw schema ingest script; dbt staging/intermediate/marts scaffold
- Cursor rules: modeling (raw→stg→int→marts), data-TDD, commit hygiene
