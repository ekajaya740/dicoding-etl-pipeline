from collections.abc import Iterator
from dataclasses import dataclass
import re
from utils.extract import RawRecord

@dataclass
class TransformedRecord:
    title: str
    price: float
    rating: float | None
    colors: int | None
    size: str | None
    gender: str | None
    timestamp: str

def transform(records: Iterator[RawRecord]) -> Iterator[TransformedRecord]:
    for raw in records:
        fields = raw.fields

        title = _clean_title(fields.get("title"))
        if title is None:
            continue

        price = _clean_price(fields.get("price"))
        if price is None:
            continue


        yield TransformedRecord(
            title=title,
            price=price,
            rating=_clean_rating(fields.get("rating")),
            colors=_clean_color_count(fields.get("colors")),
            size=_clean_after_colon(fields.get("size")),
            gender=_clean_after_colon(fields.get("gender")),
            timestamp=raw.timestamp,
        )

def _convert_rupiah(value: float, rate: float) -> float:
    return value * rate

def _clean_title(raw: str | None) -> str | None:
    if raw is None or raw in ("Unknown Product", "Invalid Product"):
        return None
    return raw

def _clean_price(raw: str | None) -> float | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d.]", "", raw)
    try:
        return _convert_rupiah(float(digits), 16000.00)
    except ValueError:
        return None

def _clean_rating(raw: str | None) -> float | None:
    if not raw:
        return None
    match = re.search(r"(\d+\.?\d*)\s*/", raw)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None

def _clean_color_count(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.search(r"\d+", raw)
    if not match:
        return None
    try:
        return int(match.group())
    except ValueError:
        return None


def _clean_after_colon(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.split(":", 1)[-1].strip() if ":" in raw else raw.strip()
