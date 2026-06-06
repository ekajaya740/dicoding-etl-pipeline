import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_load_csv_permission_denied(tmp_path: Path) -> None:
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o444)

    recs = iter([_make_record()])
    nested = readonly_dir / "sub" / "deep"

    with pytest.raises(RuntimeError, match="Failed to create output directory"):
        load(recs, "csv", output_path=nested)


def test_load_csv_wraps_oserror_from_open(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "output.csv"

    real_open = Path.open

    def fake_open(self, *args, **kwargs):
        if self == target:
            raise OSError("disk full")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)

    with pytest.raises(RuntimeError, match="Failed to write CSV"):
        load(iter([_make_record()]), "csv", output_path=tmp_path)


def test_load_unknown_target_raises() -> None:
    with pytest.raises(ValueError, match="Unknown load target"):
        load(iter([]), "mongodb")


def test_load_csv_missing_output_path_raises() -> None:
    with pytest.raises(ValueError, match="output_path"):
        load(iter([]), "csv")


def _gsheet_dependencies(monkeypatch, worksheet: MagicMock) -> MagicMock:
    creds_instance = MagicMock()
    creds_cls = MagicMock(return_value=creds_instance)
    monkeypatch.setattr("utils.load.Credentials", creds_cls)
    monkeypatch.setattr(
        "utils.load.Credentials.from_service_account_file",
        MagicMock(return_value=creds_instance),
    )
    client = MagicMock()
    client.open_by_key.return_value.worksheet.return_value = worksheet
    monkeypatch.setattr("utils.load.gspread.authorize", MagicMock(return_value=client))
    return creds_cls


def test_load_gsheet_writes_rows_and_returns_count(monkeypatch) -> None:
    worksheet = MagicMock()
    _gsheet_dependencies(monkeypatch, worksheet)

    recs = iter([_make_record(title="A"), _make_record(title="B")])
    count = load(
        recs,
        "gsheet",
        credentials_file="creds.json",
        spreadsheet_id="sheet-id",
        sheet_name="Sheet1",
    )

    assert count == 2
    worksheet.clear.assert_called_once()
    worksheet.update.assert_called_once()
    args, _ = worksheet.update.call_args
    rows = args[0]
    assert rows[0] == FIELDNAMES
    assert [row[0] for row in rows[1:]] == ["A", "B"]
    assert worksheet.format.call_count == 2


def test_load_gsheet_skips_number_format_for_empty_input(monkeypatch) -> None:
    worksheet = MagicMock()
    _gsheet_dependencies(monkeypatch, worksheet)

    count = load(
        iter([]),
        "gsheet",
        credentials_file="creds.json",
        spreadsheet_id="sheet-id",
        sheet_name="Sheet1",
    )

    assert count == 0
    worksheet.clear.assert_called_once()
    worksheet.update.assert_called_once()
    worksheet.format.assert_not_called()


def test_load_gsheet_propagates_underlying_error(monkeypatch) -> None:
    worksheet = MagicMock()
    worksheet.update.side_effect = Exception("api quota exceeded")
    _gsheet_dependencies(monkeypatch, worksheet)

    with pytest.raises(RuntimeError, match="api quota exceeded"):
        load(
            iter([_make_record()]),
            "gsheet",
            credentials_file="creds.json",
            spreadsheet_id="sheet-id",
            sheet_name="Sheet1",
        )


def test_load_gsheet_uses_real_credentials_call(monkeypatch, tmp_path: Path) -> None:
    creds_file = tmp_path / "creds.json"
    creds_file.write_text("{}")

    worksheet = MagicMock()
    creds_cls = _gsheet_dependencies(monkeypatch, worksheet)

    load(
        iter([_make_record()]),
        "gsheet",
        credentials_file=creds_file,
        spreadsheet_id="sheet-id",
        sheet_name="Sheet1",
    )

    creds_cls.from_service_account_file.assert_called_once()
    args, kwargs = creds_cls.from_service_account_file.call_args
    assert args[0] == str(creds_file)
    assert "scopes" in kwargs


def _mock_postgres(monkeypatch) -> tuple[MagicMock, MagicMock, MagicMock]:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr("utils.load.psycopg2.connect", MagicMock(return_value=conn))
    execute_values = MagicMock()
    monkeypatch.setattr("utils.load.execute_values", execute_values)
    return conn, cursor, execute_values


def test_load_postgresql_writes_rows_and_returns_count(monkeypatch) -> None:
    conn, cursor, execute_values = _mock_postgres(monkeypatch)

    recs = iter([_make_record(title="A"), _make_record(title="B")])
    count = load(
        recs,
        "postgresql",
        host="db",
        port=5432,
        dbname="etl",
        user="u",
        password="p",
        table="products",
    )

    assert count == 2
    cursor.execute.assert_called_once()
    conn.commit.assert_called_once()
    conn.close.assert_called_once()
    execute_values.assert_called_once()
    insert_sql = execute_values.call_args.args[1]
    assert "INSERT INTO" in str(insert_sql)
    assert "VALUES %s" in str(insert_sql)
    assert execute_values.call_args.args[1]._wrapped[1].string == "products"


def test_load_postgresql_empty_input_does_not_call_execute_values(monkeypatch) -> None:
    conn, cursor, execute_values = _mock_postgres(monkeypatch)

    count = load(
        iter([]),
        "postgresql",
        host="db",
        dbname="etl",
        user="u",
        password="p",
        table="products",
    )

    assert count == 0
    cursor.execute.assert_called_once()
    execute_values.assert_not_called()
    conn.commit.assert_called_once()
    conn.close.assert_called_once()


def test_load_postgresql_wraps_operational_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "utils.load.psycopg2.connect",
        MagicMock(side_effect=psycopg2.OperationalError("connection refused")),
    )

    with pytest.raises(RuntimeError, match="Failed to connect to PostgreSQL"):
        load(
            iter([_make_record()]),
            "postgresql",
            host="db",
            dbname="etl",
            user="u",
            password="p",
            table="products",
        )


def test_load_postgresql_closes_connection_on_exception(monkeypatch) -> None:
    conn = MagicMock()
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("schema error")
    conn.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr("utils.load.psycopg2.connect", MagicMock(return_value=conn))

    with pytest.raises(RuntimeError):
        load(
            iter([_make_record()]),
            "postgresql",
            host="db",
            dbname="etl",
            user="u",
            password="p",
            table="products",
        )

    conn.close.assert_called_once()
