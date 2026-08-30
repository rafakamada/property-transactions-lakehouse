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
    assert config.csv_datasets == {}


def test_load_ingest_config_csv_datasets(tmp_path: Path) -> None:
    path = tmp_path / "ingest_landing.yml"
    raw = _minimal_config_dict()
    raw["csv_datasets"] = {
        "cep_aberto": {
            "table": "cep_aberto",
            "glob": "cep_aberto/*.csv",
            "header": False,
            "all_varchar": True,
            "columns": [
                "cep",
                "logradouro",
                "complemento",
                "bairro",
                "id_cidade",
                "id_bairro",
            ],
        }
    }
    path.write_text(yaml.dump(raw), encoding="utf-8")

    config = load_ingest_config(path)

    dataset = config.csv_datasets["cep_aberto"]
    assert dataset.table == "cep_aberto"
    assert dataset.glob == "cep_aberto/*.csv"
    assert dataset.header is False
    assert dataset.columns[0] == "cep"
    assert dataset.columns[-1] == "id_bairro"


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


def test_resolve_csv_paths_and_ingest_union(tmp_path: Path) -> None:
    from ingest_raw import CsvDatasetConfig, ingest_csv_dataset, resolve_csv_paths

    landing = tmp_path / "landing"
    cep_dir = landing / "cep_aberto"
    cep_dir.mkdir(parents=True)
    (cep_dir / "sp.cepaberto_parte_1.csv").write_text(
        "01001000,Praça da Sé,- lado ímpar,Sé,8966,26\n",
        encoding="utf-8",
    )
    (cep_dir / "sp.cepaberto_parte_2.csv").write_text(
        '01001001,Praça da Sé,- lado par,"Sítios ""Rober""",8966,26\n',
        encoding="utf-8",
    )

    dataset = CsvDatasetConfig(
        key="cep_aberto",
        table="cep_aberto",
        glob="cep_aberto/sp.cepaberto_parte_*.csv",
        header=False,
        all_varchar=True,
        columns=(
            "cep",
            "logradouro",
            "complemento",
            "bairro",
            "id_cidade",
            "id_bairro",
        ),
    )
    paths = resolve_csv_paths(landing, dataset)
    assert [p.name for p in paths] == [
        "sp.cepaberto_parte_1.csv",
        "sp.cepaberto_parte_2.csv",
    ]

    import duckdb

    db_path = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE SCHEMA raw")
        table = ingest_csv_dataset(con, landing, dataset, "2026-01-01T00:00:00+00:00")
        assert table == "raw.cep_aberto"
        rows = con.execute(
            "SELECT cep, bairro, _source_file FROM raw.cep_aberto ORDER BY cep"
        ).fetchall()
    finally:
        con.close()

    assert rows == [
        ("01001000", "Sé", "cep_aberto/sp.cepaberto_parte_1.csv"),
        ("01001001", 'Sítios "Rober"', "cep_aberto/sp.cepaberto_parte_2.csv"),
    ]


def test_resolve_csv_paths_missing(tmp_path: Path) -> None:
    from ingest_raw import CsvDatasetConfig, resolve_csv_paths

    dataset = CsvDatasetConfig(
        key="cep_aberto",
        table="cep_aberto",
        glob="cep_aberto/*.csv",
        columns=("cep",),
    )
    with pytest.raises(IngestConfigError, match="no files matched"):
        resolve_csv_paths(tmp_path, dataset)


def test_ingest_headered_csv_projects_columns(tmp_path: Path) -> None:
    from ingest_raw import CsvDatasetConfig, ingest_csv_dataset

    landing = tmp_path / "landing"
    ipca_dir = landing / "ipca"
    ipca_dir.mkdir(parents=True)
    (ipca_dir / "IBGE_IPCA.csv").write_text(
        "Date,IPCA Rate (last 12 months),extra_ignored\n"
        "01/2024,4.51,should-not-appear\n",
        encoding="utf-8",
    )

    dataset = CsvDatasetConfig(
        key="ipca",
        table="ipca",
        glob="ipca/IBGE_IPCA.csv",
        header=True,
        all_varchar=True,
        columns=("Date", "IPCA Rate (last 12 months)"),
    )

    import duckdb

    db_path = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE SCHEMA raw")
        table = ingest_csv_dataset(con, landing, dataset, "2026-01-01T00:00:00+00:00")
        assert table == "raw.ipca"
        cols = [
            row[0]
            for row in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'raw' AND table_name = 'ipca' "
                "ORDER BY ordinal_position"
            ).fetchall()
        ]
        rows = con.execute(
            'SELECT "Date", "IPCA Rate (last 12 months)", _source_file FROM raw.ipca'
        ).fetchall()
    finally:
        con.close()

    assert cols == [
        "Date",
        "IPCA Rate (last 12 months)",
        "_source_file",
        "_loaded_at",
    ]
    assert rows == [("01/2024", "4.51", "ipca/IBGE_IPCA.csv")]
