from datetime import datetime
from html import unescape
import re
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests

from config import HACKERS_AND_DESIGNERS_ACTIVITIES_URL, REQUEST_TIMEOUT
from models import Event


AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")


class HackersAndDesignersClient:
    def __init__(
        self,
        activities_url: str = HACKERS_AND_DESIGNERS_ACTIVITIES_URL,
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        self.activities_url = activities_url
        self.timeout = timeout

    def get_events(self) -> list[Event]:
        response = requests.get(self.activities_url, timeout=self.timeout)
        response.raise_for_status()

        events = []
        for item in self._extract_upcoming_items(response.text):
            try:
                events.append(self._parse_detail(item))
            except (KeyError, TypeError, ValueError) as error:
                print(
                    "Skipping malformed Hackers & Designers event "
                    f"({item.get('title', 'Unknown event')}): {error}"
                )

        return events

    def _parse_detail(self, item: dict[str, str]) -> Event:
        detail_html = self._fetch(item["url"])
        info = self._extract_info_table(detail_html)

        date = info.get("date") or item["date"]
        start, end = self._parse_date_time(date, info.get("time", ""))

        title = self._extract_title(detail_html) or item["title"]
        location = info.get("at", "")
        event_type = info.get("type", item.get("type", ""))
        description = self._extract_description(detail_html)
        uid = item["id"] or item["url"]

        return Event(
            radar_id=f"hackersanddesigners:{uid}",
            uuid=f"hackersanddesigners:{uid}",
            title=title,
            start=start,
            end=end,
            url=item["url"],
            description=description,
            location=location,
            categories=[event_type] if event_type else [],
            topics=["Hackers & Designers"],
            source="hackersanddesigners",
        )

    def _fetch(self, url: str) -> str:
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _extract_upcoming_items(self, html: str) -> list[dict[str, str]]:
        match = re.search(
            r'<ul class="events" aria-label="Upcoming activities">(.*?)</ul>',
            html,
            flags=re.DOTALL,
        )
        if not match:
            return []

        items = []
        for raw_item in re.findall(r"<li\b(.*?)</li>", match.group(1), re.DOTALL):
            id_match = re.search(r'\bid="([^"]+)"', raw_item)
            type_match = re.search(r'\bdata-type="([^"]+)"', raw_item)
            date_match = re.search(r'\bdata-start="([^"]+)"', raw_item)
            href_match = re.search(r'<a href="([^"]+)"', raw_item)
            title_match = re.search(
                r'<span class="mw-page-title-main">(.*?)</span>',
                raw_item,
                flags=re.DOTALL,
            )

            if not date_match or not href_match or not title_match:
                continue

            items.append(
                {
                    "id": self._clean_text(id_match.group(1)) if id_match else "",
                    "type": self._clean_text(type_match.group(1)) if type_match else "",
                    "date": self._clean_text(date_match.group(1)),
                    "url": urljoin(self.activities_url, href_match.group(1)),
                    "title": self._clean_text(title_match.group(1)),
                }
            )

        return items

    def _extract_info_table(self, html: str) -> dict[str, str]:
        info = {}

        for label, value in re.findall(
            r'<tr aria-label="[^"]+">\s*<td>(.*?)</td>\s*<td>(.*?)</td>',
            html,
            flags=re.DOTALL,
        ):
            info[self._clean_text(label).lower()] = self._clean_text(value)

        return info

    def _extract_title(self, html: str) -> str:
        match = re.search(
            r"<h1>\s*<span[^>]*>(.*?)</span>\s*</h1>",
            html,
            flags=re.DOTALL,
        )
        return self._clean_text(match.group(1)) if match else ""

    def _extract_description(self, html: str) -> str:
        match = re.search(
            r'<div class="mw-parser-output">(.*?)<!--',
            html,
            flags=re.DOTALL,
        )
        if not match:
            return ""

        text = re.sub(r"<table\b.*?</table>", " ", match.group(1), flags=re.DOTALL)
        return self._clean_text(text)

    @staticmethod
    def _parse_date_time(date: str, time: str) -> tuple[datetime, datetime | None]:
        start_date = datetime.strptime(date.replace("/", "-"), "%Y-%m-%d").date()

        if not time:
            return datetime.combine(start_date, datetime.min.time(), AMSTERDAM_TZ), None

        parts = re.split(r"\s*[-–—]\s*", time, maxsplit=1)
        start_time = datetime.strptime(parts[0].strip(), "%H:%M").time()
        start = datetime.combine(start_date, start_time, AMSTERDAM_TZ)

        if len(parts) == 1:
            return start, None

        end_time = datetime.strptime(parts[1].strip(), "%H:%M").time()
        end = datetime.combine(start_date, end_time, AMSTERDAM_TZ)
        return start, end

    @staticmethod
    def _clean_text(value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", value)
        text = unescape(text)
        return re.sub(r"\s+", " ", text).strip()
