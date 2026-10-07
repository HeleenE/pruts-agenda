from dataclasses import dataclass
from datetime import datetime, timedelta
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlparse

import requests

from config import (
    PAKHUIS_DE_ZWIJGER_AGENDA_URL,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
)
from dates import LOCAL_TIMEZONE
from models import Event


TECHNOLOGY_DOMAIN_ID = "1066"
MONTHS = {
    "jan": 1, "january": 1, "januari": 1,
    "feb": 2, "february": 2, "februari": 2,
    "mar": 3, "march": 3, "maart": 3,
    "apr": 4, "april": 4,
    "may": 5, "mei": 5,
    "jun": 6, "june": 6, "juni": 6,
    "jul": 7, "july": 7, "juli": 7,
    "aug": 8, "august": 8, "augustus": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "okt": 10, "october": 10, "oktober": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


@dataclass
class _AgendaCard:
    year: int
    month: int
    url: str = ""
    title: str = ""
    subtitle: str = ""
    date_time: str = ""
    location: str = ""


class PakhuisDeZwijgerClient:
    def __init__(
        self,
        agenda_url: str = PAKHUIS_DE_ZWIJGER_AGENDA_URL,
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        self.agenda_url = agenda_url.rstrip("/")
        self.api_url = urljoin(f"{self.agenda_url}/", "../ajax/agenda/getItems")
        self.timeout = timeout

    def get_events(self) -> list[Event]:
        cards: dict[str, _AgendaCard] = {}
        now = datetime.now(LOCAL_TIMEZONE)
        page = 1
        previous_date = ""
        with requests.Session() as session:
            session.headers.update(REQUEST_HEADERS)
            agenda_response = session.get(self.agenda_url, timeout=self.timeout)
            _raise_with_diagnostics(agenda_response, "agenda session")

            while True:
                response = session.get(
                    self.api_url,
                    params={
                        "page": page,
                        "prev_date": previous_date,
                        "domains[]": TECHNOLOGY_DOMAIN_ID,
                    },
                    headers={
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "Referer": self.agenda_url,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    timeout=self.timeout,
                )
                _raise_with_diagnostics(response, f"agenda AJAX page {page}")
                try:
                    payload = response.json()
                    html = payload["data"]
                    total_pages = int(payload["total_pages"])
                    previous_date = str(payload.get("last_date", ""))
                except (KeyError, TypeError, ValueError) as error:
                    raise requests.RequestException(
                        "Pakhuis de Zwijger returned an unexpected agenda response "
                        f"({_response_diagnostics(response)})"
                    ) from error
                for card in _extract_agenda_cards(html, now.year, now.month):
                    if card.url:
                        cards[urljoin(self.agenda_url, card.url)] = card
                if page >= total_pages:
                    break
                page += 1

        events = []
        for url, card in cards.items():
            try:
                events.append(_card_to_event(card, url))
            except ValueError as error:
                print(f"Skipping malformed Pakhuis de Zwijger event ({card.title}): {error}")
        return events


def _raise_with_diagnostics(response: requests.Response, request_name: str) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        raise requests.RequestException(
            f"Pakhuis de Zwijger {request_name} failed "
            f"({_response_diagnostics(response)})"
        ) from error


def _response_diagnostics(response: requests.Response) -> str:
    content_type = response.headers.get("Content-Type", "unknown")
    server = response.headers.get("Server", "unknown")
    body = re.sub(r"\s+", " ", response.text).strip()[:240]
    return (
        f"HTTP {response.status_code}; content-type={content_type!r}; "
        f"server={server!r}; body={body!r}"
    )


def _extract_agenda_cards(
    html: str,
    default_year: int,
    default_month: int,
) -> list[_AgendaCard]:
    parser = _AgendaParser(default_year, default_month)
    parser.feed(html)
    parser.close()
    return parser.cards


def _card_to_event(card: _AgendaCard, url: str) -> Event:
    if not card.title:
        raise ValueError("missing title")
    start, end, all_day = _parse_date_time(card.date_time, card.year, card.month)
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    if not slug:
        raise ValueError("missing programme slug")
    event_id = f"pakhuisdezwijger:{slug}"
    return Event(
        radar_id=event_id,
        uuid=event_id,
        title=card.title,
        start=start,
        end=end,
        url=url,
        description=card.subtitle,
        location=card.location,
        source="pakhuisdezwijger",
        all_day=all_day,
    )


def _parse_date_time(
    value: str,
    default_year: int,
    default_month: int,
) -> tuple[datetime, datetime | None, bool]:
    text = re.sub(r"\s+", " ", unescape(value)).strip().lower()
    range_match = re.search(
        r"(\d{1,2})\s+([a-z]+)(?:\s+(20\d{2}))?\s*[-–]\s*"
        r"(\d{1,2})\s+([a-z]+)(?:\s+(20\d{2}))?",
        text,
    )
    if range_match:
        start_day, start_month_name, start_year, end_day, end_month_name, end_year = range_match.groups()
        start_month = _month_number(start_month_name)
        end_month = _month_number(end_month_name)
        start_year_value = int(start_year or default_year)
        end_year_value = int(end_year or start_year_value)
        if not end_year and end_month < start_month:
            end_year_value += 1
        start = datetime(start_year_value, start_month, int(start_day), tzinfo=LOCAL_TIMEZONE)
        end = datetime(end_year_value, end_month, int(end_day), tzinfo=LOCAL_TIMEZONE) + timedelta(days=1)
        return start, end, True

    date_match = re.search(
        r"(?:[a-z]+\s+)?(\d{1,2})\s+([a-z]+)(?:\s+(20\d{2}))?"
        r"(?:,\s*(\d{1,2})[.:](\d{2}))?",
        text,
    )
    if not date_match:
        raise ValueError(f"could not parse date {value!r}")
    day, month_name, year, hour, minute = date_match.groups()
    month = _month_number(month_name)
    year_value = int(year or default_year)
    if not year and month < default_month and default_month == 12:
        year_value += 1
    all_day = hour is None
    start = datetime(
        year_value,
        month,
        int(day),
        int(hour or 0),
        int(minute or 0),
        tzinfo=LOCAL_TIMEZONE,
    )
    return start, None, all_day


def _month_number(value: str) -> int:
    month = MONTHS.get(value.rstrip("."))
    if not month:
        raise ValueError(f"unknown month {value!r}")
    return month


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    return set((dict(attrs).get("class") or "").split())


class _AgendaParser(HTMLParser):
    def __init__(self, default_year: int, default_month: int) -> None:
        super().__init__()
        self.year = default_year
        self.month = default_month
        self.cards: list[_AgendaCard] = []
        self._card: _AgendaCard | None = None
        self._div_depth = 0
        self._card_depth = 0
        self._capture_name = ""
        self._capture_depth = 0
        self._capture_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = _classes(attrs)
        if tag == "div":
            self._div_depth += 1
            if {"row", "container-title"}.issubset(classes):
                match = re.match(r"(20\d{2})/(\d{2})/\d{2}", attributes.get("data-date", ""))
                if match:
                    self.year, self.month = map(int, match.groups())
            if {"program", "teaser"}.issubset(classes):
                self._card = _AgendaCard(self.year, self.month)
                self._card_depth = self._div_depth
            if self._card:
                fields = {
                    "title": "title",
                    "subtitle": "subtitle",
                    "date-time": "date_time",
                    "location": "location",
                }
                for class_name, field_name in fields.items():
                    if class_name in classes:
                        self._capture_name = field_name
                        self._capture_depth = self._div_depth
                        self._capture_parts = []
                        break
        elif tag == "a" and self._card and "program-link" in classes:
            self._card.url = attributes.get("href", "")

    def handle_data(self, data: str) -> None:
        if self._capture_name:
            self._capture_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "div":
            return
        if self._capture_name and self._capture_depth == self._div_depth:
            value = re.sub(r"\s+", " ", "".join(self._capture_parts)).strip()
            if self._card:
                setattr(self._card, self._capture_name, value)
            self._capture_name = ""
            self._capture_parts = []
        if self._card and self._card_depth == self._div_depth:
            self.cards.append(self._card)
            self._card = None
        self._div_depth -= 1
