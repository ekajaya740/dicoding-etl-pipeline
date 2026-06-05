import pytest
import requests
from unittest.mock import MagicMock
from utils.extract import _parse, _fetch, RawRecord

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


def test_fetch_raises_on_network_error():
    session = MagicMock()
    session.get.side_effect = requests.ConnectionError
    result = _fetch(session, "http://example.com")
    assert result == ""


def test_fetch_raises_on_http_error():
    session = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError
    session.get.return_value = mock_response
    result = _fetch(session, "http://example.com")
    assert result == ""
