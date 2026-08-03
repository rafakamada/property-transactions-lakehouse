"""Unit tests for ingest_raw helpers."""

from pathlib import Path

import pytest
from ingest_raw import (
    TableNameCollisionError,
    find_excel_files,
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
