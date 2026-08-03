"""Ingest landing XLSX files into DuckDB schema `raw` as-is.

Usage:
    uv run python scripts/ingest_raw.py

Place yearly `.xlsx` / `.xlsm` files in `data/landing/` (one sheet per month).
Each file becomes `raw.<stem>` with source columns preserved, plus
`_source_file` and `_loaded_at` metadata columns. Re-running replaces the
table for that file (full replace — not incremental). See docs/modeling.md.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
LANDING_DIR = REPO_ROOT / "data" / "landing"
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}


def find_excel_files(landing_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in landing_dir.iterdir()
        if p.is_file() and p.suffix.lower() in EXCEL_SUFFIXES
    )


def sanitize_table_name(stem: str) -> str:
    name = "".join(c if c.isalnum() or c == "_" else "_" for c in stem.lower())
    if not name or name[0].isdigit():
        name = f"t_{name}"
    return name


def ingest(files: list[Path], db_path: Path) -> list[str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    created: list[str] = []
    try:
        con.execute("INSTALL excel;")
        con.execute("LOAD excel;")
        con.execute("CREATE SCHEMA IF NOT EXISTS raw;")
        loaded_at = datetime.now(UTC).isoformat()
        for path in files:
            table = sanitize_table_name(path.stem)
            # Preserve source columns; append technical metadata only.
            con.execute(
                f"""
                CREATE OR REPLACE TABLE raw.{table} AS
                SELECT
                    *,
                    ? AS _source_file,
                    ? AS _loaded_at
                FROM read_xlsx(?, header := true)
                """,
                [path.name, loaded_at, str(path)],
            )
            created.append(f"raw.{table}")
            print(f"ingested {path.name} -> raw.{table}")
    finally:
        con.close()
    return created


def main() -> int:
    if not LANDING_DIR.exists():
        print(f"error: landing directory not found: {LANDING_DIR}", file=sys.stderr)
        return 1

    files = find_excel_files(LANDING_DIR)
    if not files:
        print(
            f"error: no .xlsx/.xlsm files found in {LANDING_DIR}",
            file=sys.stderr,
        )
        return 1

    created = ingest(files, DB_PATH)
    print(f"done: {len(created)} table(s) in {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
