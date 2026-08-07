"""Seed a minimal DuckDB `raw` schema for CI dbt run/test.

Landing XLSX files are gitignored, so CI cannot run full ingest. This script
creates `raw.itbi_YYYY` tables (matching `vars.itbi_years` / ingest column
contract) with a few synthetic rows so `stg_itbi` and dbt tests can run.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "ingest_landing.yml"
DBT_PROJECT = ROOT / "dbt_project.yml"
DB_PATH = ROOT / "data" / "dev.duckdb"

METADATA = ("_source_file", "_source_sheet", "_loaded_at", "_reference_month")


def _itbi_years() -> list[int]:
    raw = yaml.safe_load(DBT_PROJECT.read_text(encoding="utf-8")) or {}
    years = (raw.get("vars") or {}).get("itbi_years")
    if not years:
        raise SystemExit("dbt_project.yml vars.itbi_years is missing or empty")
    return [int(y) for y in years]


def _transaction_columns() -> list[str]:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    cols = (raw.get("defaults") or {}).get("transaction_columns")
    if not cols:
        raise SystemExit("ingest_landing.yml defaults.transaction_columns missing")
    return list(cols)


def _sample_value(column: str, year: int, row: int) -> str:
    """Return a varchar sample suitable for staging casts."""
    # Compare on ASCII-folded text so accents in source headers do not matter.
    folded = (
        column.lower()
        .replace("á", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    if "data de transacao" in folded:
        return str(45200 + row + (year - 2024))
    if "proporcao" in folded:
        return "100.0"
    if (
        "valor" in folded
        or "area" in folded
        or "testada" in folded
        or "fracao" in folded
    ):
        return str(1000.0 * (row + 1))
    if column.startswith("N°") or "cadastro" in folded:
        return f"{year}000{row}"
    if "natureza" in folded:
        return "1.Compra e venda"
    if "cep" in folded:
        return "01001000"
    return f"sample-{year}-{row}"


def seed(db_path: Path = DB_PATH) -> None:
    years = _itbi_years()
    columns = _transaction_columns()
    loaded_at = datetime.now(UTC).isoformat()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        for year in years:
            table = f"itbi_{year}"
            col_defs = ", ".join(f'"{c}" VARCHAR' for c in columns)
            meta_defs = (
                "_source_file VARCHAR, "
                "_source_sheet VARCHAR, "
                "_loaded_at VARCHAR, "
                "_reference_month VARCHAR"
            )
            con.execute(
                f'CREATE OR REPLACE TABLE raw."{table}" ({col_defs}, {meta_defs})'
            )

            for row in range(2):
                values: list[str] = []
                for col in columns:
                    values.append(_sample_value(col, year, row))
                values.extend(
                    [
                        f"{year}.xlsx",
                        f"JAN-{year}",
                        loaded_at,
                        f"{year}-01-01",
                    ]
                )
                placeholders = ", ".join("?" for _ in values)
                quoted_cols = ", ".join(
                    f'"{c}"' for c in list(columns) + list(METADATA)
                )
                con.execute(
                    f'INSERT INTO raw."{table}" ({quoted_cols}) '
                    f"VALUES ({placeholders})",
                    values,
                )
            print(f"seeded raw.{table} ({2} rows)")
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DB_PATH,
        help=f"DuckDB file to create (default: {DB_PATH})",
    )
    args = parser.parse_args(argv)
    seed(args.db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
