from datetime import datetime
from html import unescape
import re
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests

from config import (
    PAKHUIS_DE_ZWIJGER_TECHNOLOGY_URL,
    REQUEST_TIMEOUT,
)
from models import Event


AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")
PAKHUIS_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Referer": "https://dezwijger.nl/agenda",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
}
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mrt": 3,
    "apr": 4,
    "mei": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "okt": 10,
    "nov": 11,
    "dec": 12,
}


class PakhuisDeZwijgerClient:
    def __init__(
        self,
        agenda_url: str = PAKHUIS_DE_ZWIJGER_TECHNOLOGY_URL,
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        self.agenda_url = agenda_url
        self.timeout = timeout

    def get_events(self) -> list[Event]:
        response = requests.get(
            self.agenda_url,
            headers=PAKHUIS_REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()

        events = []
        for raw_event in _extract_event_cards(response.text):
            try:
                events.append(_card_to_event(raw_event, self.agenda_url))
            except (KeyError, TypeError, ValueError) as error:
                title = raw_event.get("title", "Unknown event")
                print(f"Skipping malformed Pakhuis de Zwijger event ({title}): {error}")
        return events


def _extract_event_cards(html: str) -> list[dict[str, str]]:
    marker = re.compile(
        r'<div class="row container-title" data-date="(?P<month>\d{4}/\d{2})/\d{2}">'
        r'|<a href="(?P<path>/programma/[^"]+)" class="program-link"></a>'
    )
    matches = list(marker.finditer(html))
    current_month = ""
    cards = []

    for index, match in enumerate(matches):
        if match.group("month"):
            current_month = match.group("month")
            continue
        if not current_month:
            continue

        end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
        card_html = html[match.end():end]
        cards.append(
            {
                "month": current_month,
                "path": match.group("path"),
                "title": _class_text(card_html, "title truncate"),
                "description": _class_text(card_html, "subtitle truncate"),
                "date_time": _class_text(card_html, "date-time"),
                "location": _class_text(card_html, "location"),
            }
        )

    return cards


def _card_to_event(card: dict[str, str], base_url: str) -> Event:
    start = _parse_start(card["month"], card["date_time"])
    url = urljoin(base_url, card["path"])
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    if not slug or not card["title"]:
        raise ValueError("missing event identity")

    return Event(
        radar_id=f"pakhuisdezwijger:{slug}",
        uuid=f"pakhuisdezwijger:{slug}",
        title=card["title"],
        start=start,
        end=None,
        url=url,
        description=card["description"],
        location=card["location"],
        categories=[],
        topics=["Pakhuis de Zwijger"],
        source="Pakhuis de Zwijger",
    )


def _parse_start(month: str, date_time: str) -> datetime:
    match = re.search(
        r"(?:\w+\s+)?(\d{1,2})\s+([a-z]+),\s+(\d{1,2})[.:](\d{2})",
        date_time.lower(),
    )
    if not match:
        raise ValueError(f"could not parse date and time: {date_time}")

    day, month_name, hour, minute = match.groups()
    year, expected_month = (int(part) for part in month.split("/"))
    parsed_month = MONTHS.get(month_name)
    if parsed_month is None or parsed_month != expected_month:
        raise ValueError(f"unexpected month in date and time: {date_time}")

    return datetime(
        year,
        parsed_month,
        int(day),
        int(hour),
        int(minute),
        tzinfo=AMSTERDAM_TZ,
    )


def _class_text(html: str, class_name: str) -> str:
    match = re.search(
        rf'<div[^>]*class="{re.escape(class_name)}"[^>]*>(.*?)</div>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        return ""
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    return re.sub(r"\s+", " ", unescape(text)).strip()
