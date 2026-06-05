import csv
from pathlib import Path

import gspread
import psycopg2
import pytest

from utils.load import FIELDNAMES, load
from utils.transform import TransformedRecord


def _make_record(**overrides: str | float | int | None) -> TransformedRecord:
    defaults: dict[str, str | float | int | None] = {
        "title": "Test Product",
        "price": 1600000.0,
        "rating": 4.5,
        "colors": 3,
        "size": "M",
        "gender": "Unisex",
        "timestamp": "2026-06-05T00:00:00+00:00",
    }
    return TransformedRecord(**{**defaults, **overrides})  # type: ignore[arg-type]


def _find_csv(dir: Path) -> Path:
    files = list(dir.glob("*.csv"))
    assert len(files) == 1
    return files[0]


def test_load_writes_csv(tmp_path: Path) -> None:
    count = load(iter([_make_record()]), "csv", output_path=tmp_path)
    assert count == 1

    output = _find_csv(tmp_path)
    with output.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["title"] == "Test Product"
    assert rows[0]["price"] == "1600000.0"
    assert rows[0]["rating"] == "4.5"
    assert rows[0]["colors"] == "3"
    assert rows[0]["size"] == "M"
    assert rows[0]["gender"] == "Unisex"


def test_load_creates_parent_dirs(tmp_path: Path) -> None:
    output_dir = tmp_path / "deep" / "nested"
    count = load(iter([_make_record()]), "csv", output_path=output_dir)
    assert count == 1

    output = _find_csv(output_dir)
    assert output.exists()


def test_load_empty_input_creates_header_only(tmp_path: Path) -> None:
    count = load(iter([]), "csv", output_path=tmp_path)
    assert count == 0

    output = _find_csv(tmp_path)
    with output.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert rows == []
    assert reader.fieldnames == FIELDNAMES


def test_load_writes_none_optionals_as_empty(tmp_path: Path) -> None:
    rec = _make_record(rating=None, colors=None, size=None, gender=None)
    count = load(iter([rec]), "csv", output_path=tmp_path)
    assert count == 1

    output = _find_csv(tmp_path)
    with output.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)

    assert row["rating"] == ""
    assert row["colors"] == ""
    assert row["size"] == ""
    assert row["gender"] == ""
    assert row["title"] == "Test Product"
    assert row["price"] == "1600000.0"


def test_load_multiple_records(tmp_path: Path) -> None:
    recs = iter(
        [
            _make_record(title="A"),
            _make_record(title="B"),
            _make_record(title="C"),
        ]
    )
    count = load(recs, "csv", output_path=tmp_path)
    assert count == 3

    output = _find_csv(tmp_path)
    with output.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert [r["title"] for r in rows] == ["A", "B", "C"]


def test_load_csv_is_valid_utf8(tmp_path: Path) -> None:
    recs = iter([_make_record(title="Café – Niño 😀")])
    count = load(recs, "csv", output_path=tmp_path)
    assert count == 1

    output = _find_csv(tmp_path)
    raw = output.read_bytes()
    assert raw.decode("utf-8")
    lines = raw.decode("utf-8").strip().split("\r\n")
    assert len(lines) == 2
    assert "Café – Niño 😀" in lines[1]


def test_load_unknown_target_raises() -> None:
    with pytest.raises(ValueError, match="Unknown load target"):
        load(iter([]), "mongodb")


def test_load_csv_missing_output_path_raises() -> None:
    with pytest.raises(ValueError, match="output_path"):
        load(iter([]), "csv")




def test_load_gsheet_rejects_bad_credentials(tmp_path: Path) -> None:
    bogus = tmp_path / "not_a_key.json"
    bogus.write_text("not json")

    recs = iter([_make_record()])

    with pytest.raises(RuntimeError):
        load(
            recs,
            "gsheet",
            credentials_file=bogus,
            spreadsheet_id="fake-id",
            sheet_name="Sheet1",
        )


def test_load_csv_permission_denied(tmp_path: Path) -> None:
    """_load_csv wraps PermissionError in RuntimeError."""
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o444)

    recs = iter([_make_record()])
    nested = readonly_dir / "sub" / "deep"

    with pytest.raises(RuntimeError, match="Failed to create output directory"):
        load(recs, "csv", output_path=nested)


def test_load_gsheet_raises_on_bad_auth(tmp_path: Path) -> None:
    """Passing a non-existent credentials file raises RuntimeError."""
    recs = iter([_make_record()])
    missing = tmp_path / "nonexistent_creds.json"

    with pytest.raises(RuntimeError):
        load(
            recs,
            "gsheet",
            credentials_file=missing,
            spreadsheet_id="fake-id",
            sheet_name="Sheet1",
        )


def test_load_postgresql_connection_refused_raises_runtime_error() -> None:
    recs = iter([_make_record()])
    with pytest.raises(RuntimeError):
        load(
            recs,
            "postgresql",
            host="127.0.0.1",
            port=65432,
            dbname="nonexistent",
            user="nobody",
            password="nopass",
            table="products",
        )
