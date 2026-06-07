import csv
from datetime import datetime, timezone
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from utils.transform import TransformedRecord

FIELDNAMES: tuple[str, ...] = ("title", "price", "rating", "colors", "size", "gender", "timestamp")


def _records_to_dataframe(records: Iterator[TransformedRecord]) -> pd.DataFrame:
    rows: list[dict[str, str | float | int | None]] = []
    for rec in records:
        rows.append(
            {
                "title": rec.title,
                "price": rec.price,
                "rating": rec.rating,
                "colors": rec.colors,
                "size": rec.size,
                "gender": rec.gender,
                "timestamp": rec.timestamp,
            }
        )
    df = pd.DataFrame(rows, columns=pd.Index(FIELDNAMES, name=None))
    return df


def load(records: Iterator[TransformedRecord], target: str, **kwargs: Any) -> int:
    if target == "csv":
        output_path = kwargs.get("output_path")
        if output_path is None:
            raise ValueError("'output_path' is required for target='csv'")
        return _load_csv(records, output_path)

    if target == "gsheet":
        return _load_gsheet(records, **kwargs)

    if target == "postgresql":
        return _load_postgresql(records, **kwargs)

    raise ValueError(
        f"Unknown load target: {target!r}. "
        f"Expected one of: 'csv', 'gsheet', 'postgresql'"
    )


def _load_csv(
    records: Iterator[TransformedRecord], output_dir: str | Path
) -> int:
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except (IOError, OSError, PermissionError) as e:
        raise RuntimeError(f"Failed to create output directory '{output_dir}': {e}") from e

    output_path = output_dir / "output.csv"
    df = _records_to_dataframe(records)
    try:
        df.to_csv(output_path, index=False, encoding="utf-8")
    except (IOError, OSError, PermissionError) as e:
        raise RuntimeError(f"Failed to write CSV to '{output_path}': {e}") from e
    return len(df)


def _load_gsheet(
    records: Iterator[TransformedRecord],
    *,
    credentials_file: str | Path,
    spreadsheet_id: str,
    sheet_name: str,
    **_kwargs: Any,
) -> int:
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(
            str(credentials_file), scopes=scopes
        )
        client = gspread.authorize(creds)
        worksheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
        df = _records_to_dataframe(records)
        rows: list[list[Any]] = [FIELDNAMES]
        rows.extend(df.replace({pd.NA: None}).itertuples(index=False, name=None))
        worksheet.clear()
        worksheet.update(rows, "A1")

        num_rows = len(rows)
        if num_rows > 1:
            worksheet.format(
                f"B2:B{num_rows}",
                {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}},
            )
            worksheet.format(
                f"C2:C{num_rows}",
                {"numberFormat": {"type": "NUMBER", "pattern": "0.0"}},
            )

        return num_rows - 1
    except Exception as e:
        raise RuntimeError(str(e)) from e


def _load_postgresql(
    records: Iterator[TransformedRecord],
    *,
    host: str = "localhost",
    port: int = 5432,
    dbname: str,
    user: str,
    password: str,
    table: str,
    **_kwargs: Any,
) -> int:
    conn = None
    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=password
        )
    except psycopg2.OperationalError as e:
        raise RuntimeError(f"Failed to connect to PostgreSQL: {e}") from e
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    """CREATE TABLE IF NOT EXISTS {} (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        price DOUBLE PRECISION NOT NULL,
                        rating DOUBLE PRECISION,
                        colors INTEGER,
                        size TEXT,
                        gender TEXT,
                        timestamp TEXT NOT NULL
                    )"""
                ).format(sql.Identifier(table))
            )

            df = _records_to_dataframe(records)
            data: list[tuple[Any, ...]] = list(
                df.replace({pd.NA: None}).itertuples(index=False, name=None)
            )

            if data:
                execute_values(
                    cur,
                    sql.SQL(
                        """INSERT INTO {} (title, price, rating, colors, size, gender, timestamp)
                        VALUES %s"""
                    ).format(sql.Identifier(table)),
                    data,
                )

            conn.commit()
            return len(data)
    finally:
        if conn is not None:
            conn.close()
