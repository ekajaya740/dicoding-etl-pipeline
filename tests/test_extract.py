from unittest.mock import MagicMock, patch

import requests

from utils.extract import RawRecord, _fetch, _parse, extract


def test_parse_single_card():
    html = """
        <div class="collection-card">
            <div style="position: relative;">
                <img src="https://picsum.photos/280/350?random=2" class="collection-image" alt="T-shirt 2">
            </div>
            <div class="product-details">
                <h3 class="product-title">T-shirt 2</h3>
                <div class="price-container"><span class="price">$102.15</span></div>
                <p style="font-size: 14px; color: #777;">Rating: ⭐ 3.9 / 5</p>
                <p style="font-size: 14px; color: #777;">3 Colors</p>
                <p style="font-size: 14px; color: #777;">Size: M</p>
                <p style="font-size: 14px; color: #777;">Gender: Women</p>
            </div>
        </div>
    """
    records = list(_parse("https://fashion-studio.dicoding.dev", html))

    assert len(records) == 1
    r = records[0]

    assert r.source == "https://fashion-studio.dicoding.dev"
    assert isinstance(r.timestamp, str) and len(r.timestamp) > 0
    assert isinstance(r.fields["title"], str) and len(r.fields["title"]) > 0
    assert isinstance(r.fields["price"], str) and "$" in r.fields["price"]
    assert isinstance(r.fields["rating"], str) and "Rating" in r.fields["rating"]
    assert isinstance(r.fields["colors"], str) and "Colors" in r.fields["colors"]
    assert isinstance(r.fields["size"], str) and "Size" in r.fields["size"]
    assert isinstance(r.fields["gender"], str) and "Gender" in r.fields["gender"]


def test_parse_single_invalid_card():
    html = """
        <div class="collection-card">
            <div style="position: relative;">
                <img src="https://picsum.photos/280/350?random=1" class="collection-image" alt="Unknown Product">
            </div>
            <div class="product-details">
                <h3 class="product-title">Unknown Product</h3>
                <div class="price-container"><span class="price">$100.00</span></div>
                <p style="font-size: 14px; color: #777;">Rating: ⭐ Invalid Rating / 5</p>
                <p style="font-size: 14px; color: #777;">5 Colors</p>
                <p style="font-size: 14px; color: #777;">Size: M</p>
                <p style="font-size: 14px; color: #777;">Gender: Men</p>
            </div>
        </div>
    """
    records = list(_parse("https://fashion-studio.dicoding.dev", html))

    assert len(records) == 1
    r = records[0]

    assert r.source == "https://fashion-studio.dicoding.dev"
    assert isinstance(r.timestamp, str) and len(r.timestamp) > 0
    assert r.fields["title"] == "Unknown Product"
    assert isinstance(r.fields["rating"], str) and "Invalid Rating / 5" in r.fields["rating"]


def test_parse_empty_html_returns_nothing():
    assert list(_parse("http://example.com", "<html></html>")) == []


def test_parse_no_collection_cards_returns_nothing():
    assert list(_parse("http://example.com", "<html><body></body></html>")) == []


def test_parse_card_missing_product_details_is_skipped():
    html = """
        <div class="collection-card">
            <div style="position: relative;">
                <img src="https://picsum.photos/280/350" class="collection-image" alt="Orphan">
            </div>
        </div>
    """
    assert list(_parse("http://example.com", html)) == []


def test_parse_card_with_partial_fields_yields_none_for_missing():
    html = """
        <div class="collection-card">
            <div class="product-details">
                <h3 class="product-title">Half Card</h3>
            </div>
        </div>
    """
    records = list(_parse("http://example.com", html))
    assert len(records) == 1
    assert records[0].fields["title"] == "Half Card"
    assert records[0].fields["price"] is None
    assert records[0].fields["rating"] is None
    assert records[0].fields["colors"] is None
    assert records[0].fields["size"] is None
    assert records[0].fields["gender"] is None




def test_fetch_returns_text_on_success():
    session = MagicMock()
    response = MagicMock()
    response.text = "<html>ok</html>"
    response.raise_for_status.return_value = None
    session.get.return_value = response

    assert _fetch(session, "http://example.com") == "<html>ok</html>"
    session.get.assert_called_once_with("http://example.com", timeout=30)


def test_fetch_returns_empty_on_connection_error():
    session = MagicMock()
    session.get.side_effect = requests.ConnectionError
    assert _fetch(session, "http://example.com") == ""


def test_fetch_returns_empty_on_timeout():
    session = MagicMock()
    session.get.side_effect = requests.Timeout
    assert _fetch(session, "http://example.com") == ""


def test_fetch_returns_empty_on_http_error():
    session = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError
    session.get.return_value = mock_response
    assert _fetch(session, "http://example.com") == ""


def test_fetch_returns_empty_on_generic_request_exception():
    session = MagicMock()
    session.get.side_effect = requests.RequestException
    assert _fetch(session, "http://example.com") == ""




def _card_html(title: str, price: str) -> str:
    return f"""
        <div class="collection-card">
            <div class="product-details">
                <h3 class="product-title">{title}</h3>
                <div class="price-container"><span class="price">{price}</span></div>
                <p style="font-size: 14px; color: #777;">Rating: ⭐ 4.0 / 5</p>
                <p style="font-size: 14px; color: #777;">3 Colors</p>
                <p style="font-size: 14px; color: #777;">Size: M</p>
                <p style="font-size: 14px; color: #777;">Gender: Men</p>
            </div>
        </div>
    """


def test_extract_yields_records_for_each_url():
    fake_session = MagicMock()
    fake_session.get.side_effect = [
        MagicMock(text=_card_html("A", "$10"), raise_for_status=lambda: None),
        MagicMock(text=_card_html("B", "$20"), raise_for_status=lambda: None),
    ]

    with patch("utils.extract.requests.Session", return_value=fake_session) as session_cls:
        results = list(extract(["http://a", "http://b"]))

    assert session_cls.called
    assert fake_session.close.called
    assert [r.fields["title"] for r in results] == ["A", "B"]


def test_extract_skips_urls_with_empty_html_and_continues():
    fake_session = MagicMock()
    fake_session.get.side_effect = [
        MagicMock(text="", raise_for_status=lambda: None),
        MagicMock(text=_card_html("B", "$20"), raise_for_status=lambda: None),
    ]

    with patch("utils.extract.requests.Session", return_value=fake_session):
        results = list(extract(["http://empty", "http://b"]))

    assert [r.fields["title"] for r in results] == ["B"]


def test_extract_swallows_per_url_exceptions():
    fake_session = MagicMock()
    fake_session.get.side_effect = [
        requests.ConnectionError,
        MagicMock(text=_card_html("B", "$20"), raise_for_status=lambda: None),
    ]

    with patch("utils.extract.requests.Session", return_value=fake_session):
        results = list(extract(["http://bad", "http://b"]))

    assert [r.fields["title"] for r in results] == ["B"]


def test_extract_closes_session_even_when_url_raises():
    fake_session = MagicMock()
    fake_session.get.side_effect = RuntimeError("boom")

    with patch("utils.extract.requests.Session", return_value=fake_session):
        assert list(extract(["http://bad"])) == []

    fake_session.close.assert_called_once()


def test_extract_yields_no_records_when_all_urls_fail():
    fake_session = MagicMock()
    fake_session.get.side_effect = requests.ConnectionError

    with patch("utils.extract.requests.Session", return_value=fake_session):
        assert list(extract(["http://a", "http://b"])) == []


def test_extract_records_carry_source_url_and_timestamp():
    fake_session = MagicMock()
    fake_session.get.return_value = MagicMock(
        text=_card_html("A", "$10"), raise_for_status=lambda: None)
    url = "http://only"

    with patch("utils.extract.requests.Session", return_value=fake_session):
        records = list(extract([url]))

    assert len(records) == 1
    assert isinstance(records[0], RawRecord)
    assert records[0].source == url
    assert records[0].timestamp
