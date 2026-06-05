from utils.transform import (
    _clean_title,
    _clean_price,
    _clean_rating,
    _clean_color_count,
    _clean_after_colon,
    _convert_rupiah,
    transform,
    TransformedRecord,
)
from utils.extract import RawRecord



def test_convert_rupiah_basic():
    assert _convert_rupiah(100.0, 16000.0) == 1600000.0


def test_convert_rupiah_zero():
    assert _convert_rupiah(0.0, 16000.0) == 0.0



def test_clean_title_passes_valid():
    assert _clean_title("T-shirt 2") == "T-shirt 2"


def test_clean_title_rejects_none():
    assert _clean_title(None) is None


def test_clean_title_rejects_unknown_product():
    assert _clean_title("Unknown Product") is None


def test_clean_title_preserves_whitespace():
    assert _clean_title("  Jacket  ") == "  Jacket  "



def test_clean_price_strips_dollar():
    assert _clean_price("$102.15") == 1634400.0


def test_clean_price_handles_none():
    assert _clean_price(None) is None


def test_clean_price_handles_empty():
    assert _clean_price("") is None


def test_clean_price_handles_garbage():
    assert _clean_price("not a price") is None


def test_clean_price_handles_pure_digits():
    assert _clean_price("50") == 800000.0



def test_clean_rating_extracts_number():
    assert _clean_rating("Rating: ⭐ 3.9 / 5") == 3.9


def test_clean_rating_whole_number():
    assert _clean_rating("Rating: ⭐ 4 / 5") == 4.0


def test_clean_rating_none_input():
    assert _clean_rating(None) is None


def test_clean_rating_empty_string():
    assert _clean_rating("") is None


def test_clean_rating_invalid_pattern():
    assert _clean_rating("Invalid Rating / 5") is None



def test_clean_color_count_extracts_number():
    assert _clean_color_count("3 Colors") == 3


def test_clean_color_count_two_digits():
    assert _clean_color_count("12 Colors") == 12


def test_clean_color_count_none_input():
    assert _clean_color_count(None) is None


def test_clean_color_count_empty_string():
    assert _clean_color_count("") is None



def test_clean_after_colon_size():
    assert _clean_after_colon("Size: M") == "M"


def test_clean_after_colon_gender():
    assert _clean_after_colon("Gender: Women") == "Women"


def test_clean_after_colon_no_colon():
    assert _clean_after_colon("Plain") == "Plain"


def test_clean_after_colon_none_input():
    assert _clean_after_colon(None) is None



def _make_raw(**fields: str | None) -> RawRecord:
    return RawRecord(source="http://test", timestamp="2026-06-05T00:00:00+00:00", fields=fields)


def test_transform_happy_path():
    raw = _make_raw(
        title="T-shirt 2",
        price="$102.15",
        rating="Rating: ⭐ 3.9 / 5",
        colors="3 Colors",
        size="Size: M",
        gender="Gender: Women",
    )
    records = list(transform(iter([raw])))

    assert len(records) == 1
    r = records[0]
    assert isinstance(r, TransformedRecord)
    assert r.title == "T-shirt 2"
    assert isinstance(r.price, float)
    assert isinstance(r.rating, float)
    assert isinstance(r.colors, int)
    assert isinstance(r.size, str)
    assert isinstance(r.gender, str)


    assert isinstance(r.timestamp, str) and len(r.timestamp) > 0
def test_transform_skips_unknown_product():
    raw = _make_raw(title="Unknown Product", price="$10")
    assert list(transform(iter([raw]))) == []


def test_transform_skips_none_title():
    raw = _make_raw(price="$10")
    assert list(transform(iter([raw]))) == []


def test_transform_skips_empty_price():
    raw = _make_raw(title="Widget")
    assert list(transform(iter([raw]))) == []


def test_transform_skips_unparseable_price():
    raw = _make_raw(title="Widget", price="not a price")
    assert list(transform(iter([raw]))) == []


def test_transform_allows_missing_optional_fields():
    raw = _make_raw(title="Widget", price="$5")
    records = list(transform(iter([raw])))

    assert len(records) == 1
    assert records[0].rating is None
    assert records[0].colors is None
    assert records[0].size is None
    assert records[0].gender is None


def test_transform_handles_mixed_batch():
    good = _make_raw(title="A", price="$10",
        rating="Rating: 4 / 5", colors="2 Colors", size="Size: S", gender="Gender: Men")
    bad = _make_raw(title="Unknown Product", price="$10")
    broken = _make_raw(title="B", price="???")

    records = list(transform(iter([good, bad, broken])))
    assert len(records) == 1
    assert records[0].title == "A"


def test_transform_empty_input():
    assert list(transform(iter([]))) == []


def test_clean_title_rejects_invalid_product():
    assert _clean_title("Invalid Product") is None


def test_clean_rating_handles_value_error():
    result = _clean_rating("abc / 5")
    assert result is None


def test_clean_color_count_handles_value_error():
    result = _clean_color_count("abc")
    assert result is None


def test_transform_skips_invalid_product():
    raw = _make_raw(title="Invalid Product", price="$10")
    assert list(transform(iter([raw]))) == []