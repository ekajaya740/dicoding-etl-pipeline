import requests
import logging
from datetime import datetime, timezone
from bs4 import BeautifulSoup, Tag
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class RawRecord:
    source: str
    timestamp: str
    fields: dict[str, str | None]


def extract(urls: list[str]) -> Iterator[RawRecord]:
    session = requests.Session()
    logger = logging.getLogger(__name__)

    try:
        for url in urls:
            try:
                html = _fetch(session, url)
                if not html:
                    continue
                yield from _parse(url, html)
            except Exception as e:
                logger.error("Extract failed for %s: %s", url, e)
                continue
    finally:
        session.close()


def _fetch(session: requests.Session, url: str) -> str:
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except (requests.RequestException, requests.Timeout) as e:
        logging.getLogger(__name__).error("Fetch failed for %s: %s", url, e)
        return ""


def _parse(source: str, html: str) -> Iterator[RawRecord]:
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as e:
        logging.getLogger(__name__).error("Parse failed for %s: %s", source, e)
        return

    timestamp = datetime.now(timezone.utc).isoformat()
    for item in soup.select("div.collection-card"):
        details = item.select_one("div.product-details")
        if details is None:
            continue

        title_tag: Tag | None = details.select_one("h3.product-title")
        price_tag: Tag | None = details.select_one("span.price")

        details_p: list[Tag] = details.select("p[style]")

        rating_tag: Tag | None = details_p[0] if len(details_p) > 0 else None
        colors_tag: Tag | None = details_p[1] if len(details_p) > 1 else None
        size_tag: Tag | None = details_p[2] if len(details_p) > 2 else None
        gender_tag: Tag | None = details_p[3] if len(details_p) > 3 else None

        yield RawRecord(
            source=source,
            timestamp=timestamp,
            fields={
                "title": title_tag.text.strip() if title_tag else None,
                "price": price_tag.text.strip() if price_tag else None,
                "rating": rating_tag.text.strip() if rating_tag else None,
                "colors": colors_tag.text.strip() if colors_tag else None,
                "size": size_tag.text.strip() if size_tag else None,
                "gender": gender_tag.text.strip() if gender_tag else None,
            },
        )
