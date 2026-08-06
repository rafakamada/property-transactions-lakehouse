"""Unit tests for ingest_raw helpers and YAML contract."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from ingest_raw import (
    FileConfig,
    IngestConfigError,
    MonthSheetsConfig,
    OtherSheetConfig,
    SheetOverride,
    TableNameCollisionError,
    classify_workbook_sheets,
    find_excel_files,
    load_ingest_config,
    other_sheet_table_name,
    parse_reference_month,
    resolve_month_header,
    resolve_table_names,
    sanitize_table_name,
)


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("property_sales", "property_sales"),
        ("Property Sales", "property_sales"),
        ("2024-sales", "t_2024_sales"),
        ("sales-data.xlsx.backup", "sales_data_xlsx_backup"),
        ("___", "___"),
        ("", "t_"),
        ("9units", "t_9units"),
        ("Café-Sales", "café_sales"),  # non-ascii letters kept via isalnum
    ],
)
def test_sanitize_table_name(stem: str, expected: str) -> None:
    assert sanitize_table_name(stem) == expected


def test_find_excel_files_empty(tmp_path: Path) -> None:
    assert find_excel_files(tmp_path) == []


def test_find_excel_files_filters_and_sorts(tmp_path: Path) -> None:
    (tmp_path / "b_sales.xlsx").write_bytes(b"")
    (tmp_path / "a_sales.XLSX").write_bytes(b"")
    (tmp_path / "macro.xlsm").write_bytes(b"")
    (tmp_path / "notes.csv").write_bytes(b"")
    (tmp_path / "readme.txt").write_bytes(b"")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.xlsx").write_bytes(b"")
    (tmp_path / ".gitkeep").write_bytes(b"")

    found = find_excel_files(tmp_path)

    assert [p.name for p in found] == [
        "a_sales.XLSX",
        "b_sales.xlsx",
        "macro.xlsm",
    ]
    assert all(p.is_file() for p in found)


def test_resolve_table_names_unique(tmp_path: Path) -> None:
    a = tmp_path / "2024.xlsx"
    b = tmp_path / "2025.xlsx"
    a.write_bytes(b"")
    b.write_bytes(b"")

    assert resolve_table_names([a, b]) == {a: "t_2024", b: "t_2025"}


def test_resolve_table_names_collision_hyphen_vs_underscore(tmp_path: Path) -> None:
    hyphen = tmp_path / "a-b.xlsx"
    underscore = tmp_path / "a_b.xlsx"
    hyphen.write_bytes(b"")
    underscore.write_bytes(b"")

    with pytest.raises(TableNameCollisionError, match=r"raw\.a_b") as exc_info:
        resolve_table_names([hyphen, underscore])

    message = str(exc_info.value)
    assert "a-b.xlsx" in message
    assert "a_b.xlsx" in message


def test_resolve_table_names_collision_case_and_space(tmp_path: Path) -> None:
    spaced = tmp_path / "Property Sales.xlsx"
    snake = tmp_path / "property_sales.xlsx"
    spaced.write_bytes(b"")
    snake.write_bytes(b"")

    with pytest.raises(TableNameCollisionError, match=r"raw\.property_sales"):
        resolve_table_names([spaced, snake])


def _minimal_config_dict(**file_overrides: object) -> dict:
    base_file = {
        "year": 2024,
        "transaction_table": "itbi_2024",
        "month_sheets": {
            "pattern": "^(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)-2024$",
            "header": True,
            "overrides": {"JAN-2024": {"header": False}},
        },
        "other_sheets": {
            "LEGENDA": {"table": "legenda_2024"},
            "Tabela de USOS": {},
        },
    }
    base_file.update(file_overrides)
    return {
        "version": 1,
        "defaults": {
            "all_varchar": True,
            "transaction_range": "A1:AB",
            "stop_at_empty": True,
            "transaction_columns": ["N° do Cadastro (SQL)", "Nome do Logradouro"],
        },
        "files": {"2024.xlsx": base_file},
    }


def test_load_ingest_config_ok(tmp_path: Path) -> None:
    path = tmp_path / "ingest_landing.yml"
    path.write_text(yaml.dump(_minimal_config_dict()), encoding="utf-8")

    config = load_ingest_config(path)

    assert config.version == 1
    assert config.defaults.transaction_range == "A1:AB"
    assert config.files["2024.xlsx"].year == 2024
    assert config.files["2024.xlsx"].month_sheets.overrides["JAN-2024"].header is False


def test_load_ingest_config_rejects_bad_version(tmp_path: Path) -> None:
    path = tmp_path / "ingest_landing.yml"
    raw = _minimal_config_dict()
    raw["version"] = 99
    path.write_text(yaml.dump(raw), encoding="utf-8")

    with pytest.raises(IngestConfigError, match="unsupported ingest config version"):
        load_ingest_config(path)


def test_load_ingest_config_year_collision(tmp_path: Path) -> None:
    path = tmp_path / "ingest_landing.yml"
    raw = _minimal_config_dict()
    raw["files"]["2024b.xlsx"] = {
        "year": 2024,
        "transaction_table": "itbi_2024b",
        "month_sheets": {"pattern": "^JAN-2024$", "header": True},
        "other_sheets": {},
    }
    path.write_text(yaml.dump(raw), encoding="utf-8")

    with pytest.raises(IngestConfigError, match="same year"):
        load_ingest_config(path)


def test_parse_reference_month() -> None:
    assert parse_reference_month("MAI-2026") == date(2026, 5, 1)
    assert parse_reference_month("DEZ-2024") == date(2024, 12, 1)
    with pytest.raises(IngestConfigError, match="not a month tab"):
        parse_reference_month("LEGENDA")


def test_other_sheet_table_name_default_and_override() -> None:
    assert other_sheet_table_name("Tabela de USOS", 2024, None) == "tabela_de_usos_2024"
    assert other_sheet_table_name("Tabela de USOS", 2024, "usos_2024") == "usos_2024"


def test_resolve_month_header_override_wins() -> None:
    month_cfg = MonthSheetsConfig(
        pattern="^JAN-2024$",
        header=True,
        overrides={"JAN-2024": SheetOverride(header=False)},
    )
    assert resolve_month_header("JAN-2024", month_cfg) is False
    assert resolve_month_header("FEV-2024", month_cfg) is True


def test_classify_workbook_sheets_ok() -> None:
    file_cfg = FileConfig(
        filename="2024.xlsx",
        year=2024,
        transaction_table="itbi_2024",
        month_sheets=MonthSheetsConfig(
            pattern="^(JAN|FEV)-2024$",
            header=True,
            overrides={"JAN-2024": SheetOverride(header=False)},
        ),
        other_sheets={
            "LEGENDA": OtherSheetConfig(table="legenda_2024"),
            "Tabela de USOS": OtherSheetConfig(),
        },
    )
    months, others = classify_workbook_sheets(
        ["JAN-2024", "FEV-2024", "LEGENDA", "Tabela de USOS"],
        file_cfg,
    )
    assert months == ["JAN-2024", "FEV-2024"]
    assert set(others) == {"LEGENDA", "Tabela de USOS"}


def test_classify_workbook_sheets_unexpected() -> None:
    file_cfg = FileConfig(
        filename="2024.xlsx",
        year=2024,
        transaction_table="itbi_2024",
        month_sheets=MonthSheetsConfig(pattern="^JAN-2024$"),
        other_sheets={"LEGENDA": OtherSheetConfig()},
    )
    with pytest.raises(IngestConfigError, match="undeclared sheet"):
        classify_workbook_sheets(["JAN-2024", "LEGENDA", "MYSTERY"], file_cfg)


def test_month_data_range_shifts_when_header() -> None:
    from ingest_raw import _month_data_range

    assert _month_data_range("A1:AB", has_header_row=False) == "A1:AB"
    assert _month_data_range("A1:AB", has_header_row=True) == "A2:AB"


def test_classify_workbook_sheets_missing_other() -> None:
    file_cfg = FileConfig(
        filename="2024.xlsx",
        year=2024,
        transaction_table="itbi_2024",
        month_sheets=MonthSheetsConfig(pattern="^JAN-2024$"),
        other_sheets={
            "LEGENDA": OtherSheetConfig(),
            "EXPLICAÇÕES": OtherSheetConfig(),
        },
    )
    with pytest.raises(IngestConfigError, match="missing from workbook"):
        classify_workbook_sheets(["JAN-2024", "LEGENDA"], file_cfg)
