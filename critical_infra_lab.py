from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests

from config import CRITICAL_INFRA_LAB_URL, REQUEST_HEADERS, REQUEST_TIMEOUT
from models import Event


AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
MONTH_PATTERN = "|".join(MONTHS)


@dataclass
class _Block:
    tag: str
    text: str = ""
    links: list[str] = field(default_factory=list)


@dataclass
class _Activity:
    heading: str
    body: str
    links: list[str]


class CriticalInfraLabClient:
    def __init__(
        self,
        url: str = CRITICAL_INFRA_LAB_URL,
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        self.url = url
        self.timeout = timeout

    def get_events(self) -> list[Event]:
        response = requests.get(
            self.url,
            headers=REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()

        events = []
        for activity in _extract_upcoming_activities(response.text):
            if _is_reading_group(activity):
                continue

            try:
                activity = self._activity_with_detail(activity)
                events.append(_activity_to_event(activity, self.url))
            except (ValueError, requests.RequestException) as error:
                print(
                    "Skipping Critical Infrastructure Lab event "
                    f"({activity.heading}): {error}"
                )

        return events

    def _activity_with_detail(self, activity: _Activity) -> _Activity:
        url = _primary_url(activity.links, self.url)
        parsed = urlparse(url)
        if parsed.netloc != urlparse(self.url).netloc or "/upcoming/" not in parsed.path:
            return activity

        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        detail = _extract_detail_activity(response.text)
        return detail or activity


def _extract_upcoming_activities(html: str) -> list[_Activity]:
    parser = _BlockParser()
    parser.feed(html)

    in_upcoming = False
    current: _Activity | None = None
    activities = []

    for block in parser.blocks:
        if block.tag == "h2":
            heading = block.text.lower()
            if "upcoming activities" in heading:
                in_upcoming = True
                continue
            if in_upcoming:
                break

        if not in_upcoming:
            continue

        if block.tag == "h3" and block.text.startswith("#"):
            if current:
                activities.append(current)
            current = _Activity(block.text, "", list(block.links))
            continue

        if current and block.tag in {"h3", "p", "li"}:
            current.body = " ".join(part for part in [current.body, block.text] if part)
            current.links.extend(block.links)

    if current:
        activities.append(current)

    return activities


def _extract_detail_activity(html: str) -> _Activity | None:
    parser = _BlockParser()
    parser.feed(html)
    parser.close()

    current: _Activity | None = None
    for block in parser.blocks:
        if block.tag == "h2" and block.text.lower() not in {
            "upcoming",
            "past activities",
            "publications",
        }:
            current = _Activity(block.text, "", list(block.links))
            continue

        if current and block.tag in {"h3", "p", "li"}:
            current.body = " ".join(part for part in [current.body, block.text] if part)
            current.links.extend(block.links)

    return current


def _activity_to_event(activity: _Activity, base_url: str) -> Event:
    start, end = _parse_activity_dates(activity)
    title = _clean_heading(activity.heading)
    url = _primary_url(activity.links, base_url)
    uid = _slug(title)

    return Event(
        radar_id=f"criticalinfralab:{uid}",
        uuid=f"criticalinfralab:{uid}",
        title=title,
        start=start,
        end=end,
        url=url,
        description=activity.body,
        location=_extract_location(activity.body),
        categories=[],
        topics=["Critical Infrastructure Lab"],
        source="criticalinfralab",
        all_day=start.time() == datetime.min.time(),
    )


def _parse_activity_dates(activity: _Activity) -> tuple[datetime, datetime | None]:
    text = f"{activity.heading} {activity.body}"
    normalized = _normalize_text(text)

    date_range_match = re.search(
        rf"\b(\d{{1,2}})\s*(?:\+|&|and)?\s*(\d{{1,2}})\s+({MONTH_PATTERN})\s+(\d{{4}})\b",
        normalized,
    )
    if date_range_match:
        start_day, end_day, month_name, year = date_range_match.groups()
        month = _month_number(month_name)
        start = datetime(int(year), month, int(start_day), tzinfo=AMSTERDAM_TZ)
        end = datetime(int(year), month, int(end_day), 23, 59, tzinfo=AMSTERDAM_TZ)
        return start, end

    workshop_match = re.search(
        rf"workshop:\s*(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+of\s+({MONTH_PATTERN})\s+(\d{{4}})",
        normalized,
    )
    if workshop_match:
        start_day, end_day, month_name, year = workshop_match.groups()
        month = _month_number(month_name)
        start = datetime(int(year), month, int(start_day), tzinfo=AMSTERDAM_TZ)
        end = datetime(int(year), month, int(end_day), 23, 59, tzinfo=AMSTERDAM_TZ)
        return start, end

    timed_date_match = re.search(
        rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?!\d)(?:st|nd|rd|th)?\s+from\s+(\d{{1,2}})[.:](\d{{2}})\s*[-–]\s*(\d{{1,2}})[.:](\d{{2}})",
        normalized,
    )
    if timed_date_match:
        month_name, day, start_hour, start_minute, end_hour, end_minute = (
            timed_date_match.groups()
        )
        year = _year_from_heading(activity.heading)
        if not year:
            raise ValueError("missing year")
        month = _month_number(month_name)
        start = datetime(
            year,
            month,
            int(day),
            int(start_hour),
            int(start_minute),
            tzinfo=AMSTERDAM_TZ,
        )
        end = datetime(
            year,
            month,
            int(day),
            int(end_hour),
            int(end_minute),
            tzinfo=AMSTERDAM_TZ,
        )
        return start, end

    full_date_match = re.search(
        rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?!\d)(?:st|nd|rd|th)?",
        normalized,
    )
    if full_date_match:
        month_name, day = full_date_match.groups()
        year = _year_from_heading(activity.heading)
        if not year:
            raise ValueError("missing year")
        month = _month_number(month_name)
        return datetime(year, month, int(day), tzinfo=AMSTERDAM_TZ), None

    month_year_match = re.search(rf"\b({MONTH_PATTERN})\s+(\d{{4}})\b", normalized)
    if month_year_match:
        month_name, year = month_year_match.groups()
        return datetime(int(year), _month_number(month_name), 1, tzinfo=AMSTERDAM_TZ), None

    raise ValueError("could not parse date")


def _extract_location(text: str) -> str:
    normalized = _normalize_text(text)
    locations = [
        "Vrije Universiteit Amsterdam",
        "University Library UvA",
        "critical infrastructure lab at the University of Amsterdam",
    ]
    for location in locations:
        if location.lower() in normalized:
            return location
    return ""


def _primary_url(links: list[str], base_url: str) -> str:
    for link in links:
        if "#" in link:
            continue
        return urljoin(base_url, link)
    return base_url


def _clean_heading(value: str) -> str:
    text = re.sub(r"^#\s*", "", value)
    labels = (
        "event",
        "talk",
        "presentation",
        "panel",
        "call for contributions",
        "open reading group",
    )
    while True:
        cleaned = re.sub(
            rf"^({'|'.join(labels)})\s*(?:-\s*)?",
            "",
            text,
            flags=re.IGNORECASE,
        )
        if cleaned == text:
            break
        text = cleaned
    text = re.sub(r"\s+[A-Za-z]+\s+\d{4}$", "", text)
    return text.strip()


def _is_reading_group(activity: _Activity) -> bool:
    return "reading group" in activity.heading.lower()


def _year_from_heading(value: str) -> int | None:
    match = re.search(r"\b(20\d{2})\b", value)
    return int(match.group(1)) if match else None


def _month_number(value: str) -> int:
    try:
        return MONTHS[value.lower()]
    except KeyError as error:
        raise ValueError(f"unknown month {value}") from error


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return slug.strip("-")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip().lower()


class _BlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[_Block] = []
        self._current: _Block | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag in {"h2", "h3", "p", "li"}:
            self._finish_block()
            self._current = _Block(tag)
        if tag == "br" and self._current:
            self._current.text += " "
        if tag == "a" and self._current:
            href = dict(attrs).get("href")
            if href:
                self._current.links.append(href)

    def handle_data(self, data: str) -> None:
        if self._current:
            self._current.text += data

    def handle_endtag(self, tag: str) -> None:
        if self._current and tag == self._current.tag:
            self._finish_block()

    def close(self) -> None:
        self._finish_block()
        super().close()

    def _finish_block(self) -> None:
        if not self._current:
            return
        self._current.text = _clean_text(self._current.text)
        if self._current.text:
            self.blocks.append(self._current)
        self._current = None


def _clean_text(value: str) -> str:
    text = unescape(value)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()
