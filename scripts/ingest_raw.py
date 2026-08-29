"""Ingest landing files into DuckDB schema `raw` using a YAML contract.

Usage:
    uv run python scripts/ingest_raw.py

Place yearly `.xlsx` / `.xlsm` files in `data/landing/` as `YYYY.xlsx` and
declare their sheets in `config/ingest_landing.yml`. Month sheets are unioned
into one transaction table per year; every other declared sheet becomes its
own year-suffixed table. CSV datasets (e.g. CEP Aberto) are declared under
`csv_datasets` and unioned into one table each. Re-running replaces tables
(full replace — not incremental). See docs/modeling.md.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LANDING_DIR = REPO_ROOT / "data" / "landing"
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
CONFIG_PATH = REPO_ROOT / "config" / "ingest_landing.yml"
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}

_MONTH_ABBR = {
    "JAN": 1,
    "FEV": 2,
    "MAR": 3,
    "ABR": 4,
    "MAI": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SET": 9,
    "OUT": 10,
    "NOV": 11,
    "DEZ": 12,
}
_MONTH_SHEET_RE = re.compile(
    r"^(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)-(\d{4})$"
)

_WORKBOOK_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}


class IngestConfigError(ValueError):
    """Invalid or inconsistent ingest landing configuration."""


class TableNameCollisionError(ValueError):
    """Raised when distinct targets resolve to the same DuckDB table name."""


@dataclass(frozen=True)
class SheetOverride:
    header: bool | None = None
    range: str | None = None


@dataclass(frozen=True)
class MonthSheetsConfig:
    pattern: str
    header: bool = True
    overrides: dict[str, SheetOverride] = field(default_factory=dict)

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern)


@dataclass(frozen=True)
class OtherSheetConfig:
    table: str | None = None
    header: bool | None = None
    range: str | None = None


@dataclass(frozen=True)
class FileConfig:
    filename: str
    year: int
    transaction_table: str
    month_sheets: MonthSheetsConfig
    other_sheets: dict[str, OtherSheetConfig]


@dataclass(frozen=True)
class IngestDefaults:
    all_varchar: bool = True
    transaction_range: str = "A1:AB"
    stop_at_empty: bool = True
    transaction_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class CsvDatasetConfig:
    key: str
    table: str
    glob: str
    header: bool = False
    all_varchar: bool = True
    columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class IngestConfig:
    version: int
    defaults: IngestDefaults
    files: dict[str, FileConfig]
    csv_datasets: dict[str, CsvDatasetConfig] = field(default_factory=dict)


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


def other_sheet_table_name(sheet_name: str, year: int, explicit: str | None) -> str:
    if explicit:
        return explicit
    return f"{sanitize_table_name(sheet_name)}_{year}"


def parse_reference_month(sheet_name: str) -> date:
    match = _MONTH_SHEET_RE.match(sheet_name)
    if not match:
        raise IngestConfigError(
            f"sheet name is not a month tab (MON-YYYY): {sheet_name!r}"
        )
    month = _MONTH_ABBR[match.group(1)]
    year = int(match.group(2))
    return date(year, month, 1)


def list_sheet_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = root.find("m:sheets", _WORKBOOK_NS)
        if sheets is None:
            return []
        return [sheet.attrib["name"] for sheet in sheets if "name" in sheet.attrib]


def _parse_sheet_override(raw: dict[str, Any] | None) -> SheetOverride:
    raw = raw or {}
    return SheetOverride(
        header=raw.get("header"),
        range=raw.get("range"),
    )


def _parse_file_config(filename: str, raw: dict[str, Any]) -> FileConfig:
    required = ("year", "transaction_table", "month_sheets", "other_sheets")
    missing = [key for key in required if key not in raw]
    if missing:
        raise IngestConfigError(
            f"{filename}: missing required keys: {', '.join(missing)}"
        )

    month_raw = raw["month_sheets"]
    if "pattern" not in month_raw:
        raise IngestConfigError(f"{filename}: month_sheets.pattern is required")

    overrides: dict[str, SheetOverride] = {}
    for sheet_name, override_raw in (month_raw.get("overrides") or {}).items():
        overrides[sheet_name] = _parse_sheet_override(override_raw)

    other_sheets: dict[str, OtherSheetConfig] = {}
    for sheet_name, other_raw in (raw.get("other_sheets") or {}).items():
        other_raw = other_raw or {}
        other_sheets[sheet_name] = OtherSheetConfig(
            table=other_raw.get("table"),
            header=other_raw.get("header"),
            range=other_raw.get("range"),
        )

    return FileConfig(
        filename=filename,
        year=int(raw["year"]),
        transaction_table=str(raw["transaction_table"]),
        month_sheets=MonthSheetsConfig(
            pattern=str(month_raw["pattern"]),
            header=bool(month_raw.get("header", True)),
            overrides=overrides,
        ),
        other_sheets=other_sheets,
    )


def _parse_csv_dataset(key: str, raw: dict[str, Any]) -> CsvDatasetConfig:
    required = ("table", "glob", "columns")
    missing = [field_name for field_name in required if field_name not in raw]
    if missing:
        raise IngestConfigError(
            f"csv_datasets.{key}: missing required keys: {', '.join(missing)}"
        )
    columns = raw.get("columns") or []
    if not columns:
        raise IngestConfigError(f"csv_datasets.{key}: columns must be non-empty")
    return CsvDatasetConfig(
        key=key,
        table=str(raw["table"]),
        glob=str(raw["glob"]),
        header=bool(raw.get("header", False)),
        all_varchar=bool(raw.get("all_varchar", True)),
        columns=tuple(str(col) for col in columns),
    )


def load_ingest_config(path: Path) -> IngestConfig:
    if not path.exists():
        raise IngestConfigError(f"ingest config not found: {path}")

    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise IngestConfigError("ingest config must be a mapping")

    version = raw.get("version")
    if version != 1:
        raise IngestConfigError(f"unsupported ingest config version: {version!r}")

    defaults_raw = raw.get("defaults") or {}
    columns = defaults_raw.get("transaction_columns") or []
    if not columns:
        raise IngestConfigError("defaults.transaction_columns must be non-empty")

    defaults = IngestDefaults(
        all_varchar=bool(defaults_raw.get("all_varchar", True)),
        transaction_range=str(defaults_raw.get("transaction_range", "A1:AB")),
        stop_at_empty=bool(defaults_raw.get("stop_at_empty", True)),
        transaction_columns=tuple(str(col) for col in columns),
    )

    files_raw = raw.get("files") or {}
    csv_raw = raw.get("csv_datasets") or {}
    if not files_raw and not csv_raw:
        raise IngestConfigError(
            "files: or csv_datasets: must declare at least one landing source"
        )

    files = {
        filename: _parse_file_config(filename, file_raw)
        for filename, file_raw in files_raw.items()
    }

    by_year: dict[int, list[str]] = {}
    for filename, file_cfg in files.items():
        by_year.setdefault(file_cfg.year, []).append(filename)
    year_collisions = {year: names for year, names in by_year.items() if len(names) > 1}
    if year_collisions:
        detail = "; ".join(
            f"{year} <- [{', '.join(sorted(names))}]"
            for year, names in sorted(year_collisions.items())
        )
        raise IngestConfigError(f"multiple files claim the same year: {detail}")

    csv_datasets = {
        key: _parse_csv_dataset(key, dataset_raw)
        for key, dataset_raw in csv_raw.items()
    }

    return IngestConfig(
        version=version,
        defaults=defaults,
        files=files,
        csv_datasets=csv_datasets,
    )


def resolve_month_header(sheet_name: str, month_cfg: MonthSheetsConfig) -> bool:
    override = month_cfg.overrides.get(sheet_name)
    if override is not None and override.header is not None:
        return override.header
    return month_cfg.header


def classify_workbook_sheets(
    sheet_names: list[str], file_cfg: FileConfig
) -> tuple[list[str], dict[str, OtherSheetConfig]]:
    """Return (month_sheets, other_sheets) or raise on undeclared/missing sheets."""
    pattern = file_cfg.month_sheets.compiled()
    months: list[str] = []
    others: dict[str, OtherSheetConfig] = {}
    unexpected: list[str] = []

    for name in sheet_names:
        if pattern.match(name):
            months.append(name)
        elif name in file_cfg.other_sheets:
            others[name] = file_cfg.other_sheets[name]
        else:
            unexpected.append(name)

    if unexpected:
        raise IngestConfigError(
            f"{file_cfg.filename}: undeclared sheet(s): {', '.join(unexpected)}. "
            "Add them under other_sheets or extend month_sheets.pattern."
        )

    missing_other = sorted(set(file_cfg.other_sheets) - set(others))
    if missing_other:
        raise IngestConfigError(
            f"{file_cfg.filename}: configured other_sheets missing from workbook: "
            f"{', '.join(missing_other)}"
        )

    if not months:
        raise IngestConfigError(
            f"{file_cfg.filename}: no sheets matched month_sheets.pattern "
            f"{file_cfg.month_sheets.pattern!r}"
        )

    return months, others


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quoted_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _read_xlsx_sql(
    *,
    path: Path,
    sheet: str,
    header: bool,
    all_varchar: bool,
    range_: str | None,
    stop_at_empty: bool | None,
) -> str:
    options = [
        f"sheet := {_sql_string_literal(sheet)}",
        f"header := {'true' if header else 'false'}",
        f"all_varchar := {'true' if all_varchar else 'false'}",
    ]
    if range_ is not None:
        options.append(f"range := {_sql_string_literal(range_)}")
    if stop_at_empty is not None:
        options.append(f"stop_at_empty := {'true' if stop_at_empty else 'false'}")
    joined = ", ".join(options)
    return f"read_xlsx({_sql_string_literal(str(path))}, {joined})"


def _excel_column_letters(count: int) -> list[str]:
    """Return Excel-style column labels A, B, ... Z, AA, AB for headerless reads."""
    labels: list[str] = []
    for index in range(count):
        n = index
        letters = []
        while True:
            n, rem = divmod(n, 26)
            letters.append(chr(ord("A") + rem))
            if n == 0:
                break
            n -= 1
        labels.append("".join(reversed(letters)))
    return labels


def _month_data_range(transaction_range: str, *, has_header_row: bool) -> str:
    """Shift A1:AB → A2:AB when a header row should be skipped."""
    if not has_header_row:
        return transaction_range
    start, _, end = transaction_range.partition(":")
    if not end:
        raise IngestConfigError(
            f"transaction_range must look like A1:AB, got {transaction_range!r}"
        )
    # Replace trailing row number on the start cell (A1 → A2).
    col = "".join(ch for ch in start if ch.isalpha())
    row_digits = "".join(ch for ch in start if ch.isdigit())
    if not col or not row_digits:
        raise IngestConfigError(
            f"cannot shift transaction_range start cell: {transaction_range!r}"
        )
    return f"{col}{int(row_digits) + 1}:{end}"


def _month_select_sql(
    *,
    path: Path,
    sheet: str,
    header: bool,
    defaults: IngestDefaults,
    source_file: str,
    loaded_at: str,
    reference_month: date,
) -> str:
    # Always read as headerless + alias by position so mislabeled headers
    # (duplicate ACC, typos) do not break the contract or leak into data.
    data_range = _month_data_range(defaults.transaction_range, has_header_row=header)
    reader = _read_xlsx_sql(
        path=path,
        sheet=sheet,
        header=False,
        all_varchar=defaults.all_varchar,
        range_=data_range,
        stop_at_empty=defaults.stop_at_empty,
    )
    letters = _excel_column_letters(len(defaults.transaction_columns))
    aliases = ", ".join(
        f"{_quoted_ident(letter)} AS {_quoted_ident(col)}"
        for letter, col in zip(letters, defaults.transaction_columns, strict=True)
    )
    body = f"SELECT {aliases} FROM {reader}"

    return f"""
    SELECT
        src.*,
        {_sql_string_literal(source_file)} AS _source_file,
        {_sql_string_literal(sheet)} AS _source_sheet,
        {_sql_string_literal(loaded_at)} AS _loaded_at,
        DATE {_sql_string_literal(reference_month.isoformat())} AS _reference_month
    FROM ({body}) AS src
    """


def _assert_month_width(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    sheet: str,
    header: bool,
    defaults: IngestDefaults,
) -> None:
    data_range = _month_data_range(defaults.transaction_range, has_header_row=header)
    reader = _read_xlsx_sql(
        path=path,
        sheet=sheet,
        header=False,
        all_varchar=defaults.all_varchar,
        range_=data_range,
        stop_at_empty=defaults.stop_at_empty,
    )
    cols = [
        row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {reader}").fetchall()
    ]
    expected = len(defaults.transaction_columns)
    if len(cols) != expected:
        raise IngestConfigError(
            f"{path.name} sheet {sheet!r}: expected {expected} columns in "
            f"range {data_range!r}, got {len(cols)} ({cols})"
        )


def ingest_file(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    file_cfg: FileConfig,
    defaults: IngestDefaults,
    loaded_at: str,
) -> list[str]:
    sheet_names = list_sheet_names(path)
    months, others = classify_workbook_sheets(sheet_names, file_cfg)
    created: list[str] = []

    month_selects: list[str] = []
    for sheet in months:
        header = resolve_month_header(sheet, file_cfg.month_sheets)
        _assert_month_width(con, path, sheet, header, defaults)
        reference_month = parse_reference_month(sheet)
        month_selects.append(
            _month_select_sql(
                path=path,
                sheet=sheet,
                header=header,
                defaults=defaults,
                source_file=path.name,
                loaded_at=loaded_at,
                reference_month=reference_month,
            )
        )

    union_sql = "\nUNION ALL\n".join(f"({select})" for select in month_selects)
    tx_table = file_cfg.transaction_table
    con.execute(f"CREATE OR REPLACE TABLE raw.{_quoted_ident(tx_table)} AS {union_sql}")
    created.append(f"raw.{tx_table}")
    print(f"ingested {path.name} months -> raw.{tx_table} ({len(months)} sheets)")

    for sheet_name, other_cfg in others.items():
        table = other_sheet_table_name(sheet_name, file_cfg.year, other_cfg.table)
        header = True if other_cfg.header is None else other_cfg.header
        reader = _read_xlsx_sql(
            path=path,
            sheet=sheet_name,
            header=header,
            all_varchar=defaults.all_varchar,
            range_=other_cfg.range,
            stop_at_empty=None if other_cfg.range is None else True,
        )
        con.execute(
            f"""
            CREATE OR REPLACE TABLE raw.{_quoted_ident(table)} AS
            SELECT
                *,
                ? AS _source_file,
                ? AS _source_sheet,
                ? AS _loaded_at
            FROM {reader}
            """,
            [path.name, sheet_name, loaded_at],
        )
        created.append(f"raw.{table}")
        print(f"ingested {path.name} / {sheet_name} -> raw.{table}")

    return created


def resolve_csv_paths(landing_dir: Path, dataset: CsvDatasetConfig) -> list[Path]:
    paths = sorted(landing_dir.glob(dataset.glob))
    if not paths:
        raise IngestConfigError(
            f"csv_datasets.{dataset.key}: no files matched "
            f"{dataset.glob!r} under {landing_dir}"
        )
    non_files = [str(p) for p in paths if not p.is_file()]
    if non_files:
        raise IngestConfigError(
            f"csv_datasets.{dataset.key}: glob matched non-files: "
            f"{', '.join(non_files)}"
        )
    return paths


def _csv_select_sql(
    *,
    path: Path,
    dataset: CsvDatasetConfig,
    source_file: str,
    loaded_at: str,
) -> str:
    options = [
        f"header := {'true' if dataset.header else 'false'}",
        f"all_varchar := {'true' if dataset.all_varchar else 'false'}",
        # CEP Aberto dumps use RFC-style "" escapes inside quoted fields.
        "quote := '\"'",
        "escape := '\"'",
    ]
    if not dataset.header:
        # Name headerless columns from the contract (DuckDB columns := {name: type}).
        columns_map = ", ".join(
            f"{_sql_string_literal(col)}: {_sql_string_literal('VARCHAR')}"
            for col in dataset.columns
        )
        options.append(f"columns := {{{columns_map}}}")
    reader = f"read_csv({_sql_string_literal(str(path))}, {', '.join(options)})"
    if dataset.header:
        # Restrict to contracted column names when the file carries a header row.
        projected = ", ".join(_quoted_ident(col) for col in dataset.columns)
        body = f"SELECT {projected} FROM {reader}"
    else:
        body = f"SELECT * FROM {reader}"
    return f"""
    SELECT
        src.*,
        {_sql_string_literal(source_file)} AS _source_file,
        {_sql_string_literal(loaded_at)} AS _loaded_at
    FROM ({body}) AS src
    """


def ingest_csv_dataset(
    con: duckdb.DuckDBPyConnection,
    landing_dir: Path,
    dataset: CsvDatasetConfig,
    loaded_at: str,
) -> str:
    paths = resolve_csv_paths(landing_dir, dataset)
    selects = [
        _csv_select_sql(
            path=path,
            dataset=dataset,
            source_file=str(path.relative_to(landing_dir)),
            loaded_at=loaded_at,
        )
        for path in paths
    ]
    union_sql = "\nUNION ALL\n".join(f"({select})" for select in selects)
    table = dataset.table
    con.execute(f"CREATE OR REPLACE TABLE raw.{_quoted_ident(table)} AS {union_sql}")
    print(f"ingested csv_datasets.{dataset.key} -> raw.{table} ({len(paths)} file(s))")
    return f"raw.{table}"


def resolve_table_names(files: list[Path]) -> dict[Path, str]:
    """Legacy helper: map each file stem to a sanitized table name, or raise."""
    by_table: dict[str, list[Path]] = {}
    for path in files:
        table = sanitize_table_name(path.stem)
        by_table.setdefault(table, []).append(path)

    collisions = {table: paths for table, paths in by_table.items() if len(paths) > 1}
    if collisions:
        parts: list[str] = []
        for table, paths in sorted(collisions.items()):
            names = ", ".join(sorted(p.name for p in paths))
            parts.append(f"raw.{table} <- [{names}]")
        detail = "; ".join(parts)
        raise TableNameCollisionError(
            "distinct landing files sanitize to the same table name: "
            f"{detail}. Rename files so stems stay unique after sanitization."
        )

    return {path: sanitize_table_name(path.stem) for path in files}


def ingest(
    files: list[Path],
    db_path: Path,
    config: IngestConfig | None = None,
    config_path: Path = CONFIG_PATH,
    landing_dir: Path = LANDING_DIR,
) -> list[str]:
    if config is None:
        config = load_ingest_config(config_path)

    missing_config = [path.name for path in files if path.name not in config.files]
    if missing_config:
        raise IngestConfigError(
            "landing file(s) have no entry in ingest config: "
            + ", ".join(missing_config)
        )

    for filename in config.files:
        if filename not in {path.name for path in files}:
            print(f"warning: config entry {filename} has no file in landing; skipping")

    # Detect colliding target table names across Excel + CSV ingest targets.
    targets: dict[str, list[str]] = {}
    for path in files:
        file_cfg = config.files[path.name]
        targets.setdefault(file_cfg.transaction_table, []).append(path.name)
        for sheet_name, other_cfg in file_cfg.other_sheets.items():
            table = other_sheet_table_name(sheet_name, file_cfg.year, other_cfg.table)
            targets.setdefault(table, []).append(f"{path.name}:{sheet_name}")
    for dataset in config.csv_datasets.values():
        targets.setdefault(dataset.table, []).append(f"csv_datasets.{dataset.key}")
    collisions = {table: srcs for table, srcs in targets.items() if len(srcs) > 1}
    if collisions:
        detail = "; ".join(
            f"raw.{table} <- [{', '.join(srcs)}]"
            for table, srcs in sorted(collisions.items())
        )
        raise TableNameCollisionError(
            f"distinct ingest targets resolve to the same table name: {detail}"
        )

    if not files and not config.csv_datasets:
        raise IngestConfigError("nothing to ingest: no Excel files and no csv_datasets")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    created: list[str] = []
    try:
        if files:
            con.execute("INSTALL excel;")
            con.execute("LOAD excel;")
        con.execute("CREATE SCHEMA IF NOT EXISTS raw;")
        loaded_at = datetime.now(UTC).isoformat()
        for path in files:
            file_cfg = config.files[path.name]
            created.extend(ingest_file(con, path, file_cfg, config.defaults, loaded_at))
        for dataset in config.csv_datasets.values():
            created.append(ingest_csv_dataset(con, landing_dir, dataset, loaded_at))
    finally:
        con.close()
    return created


def main() -> int:
    if not LANDING_DIR.exists():
        print(f"error: landing directory not found: {LANDING_DIR}", file=sys.stderr)
        return 1

    try:
        config = load_ingest_config(CONFIG_PATH)
    except IngestConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    files = find_excel_files(LANDING_DIR)
    if not files and not config.csv_datasets:
        print(
            f"error: no .xlsx/.xlsm files and no csv_datasets in {LANDING_DIR}",
            file=sys.stderr,
        )
        return 1

    try:
        created = ingest(files, DB_PATH, config=config)
    except (IngestConfigError, TableNameCollisionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"done: {len(created)} table(s) in {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
