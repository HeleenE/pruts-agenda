import calendar
from datetime import datetime
from html import unescape
import re
from typing import Any

import requests

from config import (
    RADAR_API_URL,
    RADAR_PAGE_SIZE,
    RADAR_WINDOW_MONTHS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
)
from models import Event


RADAR_FIELDS = (
    "body:value",
    "category",
    "date_time",
    "offline",
    "title",
    "topic",
    "url",
    "uuid",
)


class RadarResponseError(requests.RequestException):
    pass


class RadarClient:
    def __init__(self, timeout: int = REQUEST_TIMEOUT) -> None:
        self.timeout = timeout

    def get_events(self, city: str) -> list[Event]:
        window_start = datetime.now().astimezone().replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        window_end = self._add_months(window_start, RADAR_WINDOW_MONTHS)
        raw_events = self._get_all_pages(city, window_start, window_end)

        events: list[Event] = []

        for radar_id, raw_event in raw_events.items():
            try:
                events.extend(self._parse_event(radar_id, raw_event))
            except (KeyError, TypeError, ValueError) as error:
                title = raw_event.get("title", "Unknown event")
                print(
                    f"Skipping malformed event "
                    f"{radar_id} ({title}): {error}"
                )

        return events

    def _get_all_pages(
        self,
        city: str,
        window_start: datetime,
        window_end: datetime,
    ) -> dict[str, dict[str, Any]]:
        raw_events: dict[str, dict[str, Any]] = {}
        expected_count: int | None = None
        offset = 0

        while expected_count is None or len(raw_events) < expected_count:
            response = requests.get(
                RADAR_API_URL,
                params={
                    "facets[city][]": city,
                    "filter[~and][search_api_aggregation_1][~gte]": int(
                        window_start.timestamp()
                    ),
                    "filter[~or][search_api_aggregation_1][~lt]": int(
                        window_end.timestamp()
                    ),
                    "fields": ",".join(RADAR_FIELDS),
                    "limit": RADAR_PAGE_SIZE,
                    "offset": offset,
                },
                headers=REQUEST_HEADERS,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, dict):
                raise RadarResponseError(
                    "Radar returned an unexpected response structure"
                )
            page_events = data.get("result", {})
            try:
                page_count = int(data["count"])
            except (KeyError, TypeError, ValueError) as error:
                raise RadarResponseError(
                    "Radar returned an invalid result count"
                ) from error

            if page_events is False and page_count == 0:
                page_events = {}
            if not isinstance(page_events, dict):
                raise RadarResponseError(
                    "Radar returned an unexpected result structure"
                )

            if expected_count is None:
                expected_count = page_count
            elif page_count != expected_count:
                raise RadarResponseError(
                    "Radar result count changed while fetching pages"
                )

            previous_size = len(raw_events)
            raw_events.update(page_events)
            if (
                len(raw_events) == previous_size
                and len(raw_events) < expected_count
            ):
                raise RadarResponseError(
                    "Radar pagination stopped before all events were fetched"
                )

            offset += RADAR_PAGE_SIZE

        if len(raw_events) != expected_count:
            raise RadarResponseError(
                "Radar returned an incomplete or inconsistent event set"
            )

        return raw_events

    @staticmethod
    def _add_months(value: datetime, months: int) -> datetime:
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)

    def _parse_event(
        self,
        radar_id: str,
        raw_event: dict[str, Any],
    ) -> list[Event]:
        date_ranges = raw_event.get("date_time") or []

        if not date_ranges:
            return []

        title = raw_event.get("title") or "Untitled event"
        uuid = raw_event.get("uuid") or radar_id
        url = raw_event.get("url") or ""

        body = raw_event.get("body")
        if isinstance(body, dict):
            description_html = body.get("value", "")
        else:
            description_html = ""

        description = self._strip_html(description_html)
        categories = self._extract_names(raw_event.get("category"))
        topics = self._extract_names(raw_event.get("topic"))
        location = self._extract_location(raw_event.get("offline"))

        parsed_events: list[Event] = []

        for date_range in date_ranges:
            start_string = date_range.get("time_start")

            if not start_string:
                continue

            start = self._parse_datetime(start_string)

            end_string = date_range.get("time_end")
            end = self._parse_datetime(end_string) if end_string else None

            parsed_events.append(
                Event(
                    radar_id=radar_id,
                    uuid=uuid,
                    title=title,
                    start=start,
                    end=end,
                    url=url,
                    description=description,
                    location=location,
                    categories=categories,
                    topics=topics,
                )
            )

        return parsed_events

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        return datetime.fromisoformat(value)

    @staticmethod
    def _extract_names(items: Any) -> list[str]:
        if not isinstance(items, list):
            return []

        names: list[str] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            name = item.get("name") or item.get("title")

            if name:
                names.append(str(name).strip())

        return names

    @staticmethod
    def _extract_location(items: Any) -> str:
        if not isinstance(items, list):
            return ""

        locations = []

        for item in items:
            if not isinstance(item, dict):
                continue

            title = item.get("title")

            if title:
                locations.append(str(title).strip())

        return ", ".join(locations)

    @staticmethod
    def _strip_html(value: str) -> str:
        if not value:
            return ""

        text = re.sub(r"<[^>]+>", " ", value)
        text = unescape(text)

        return re.sub(r"\s+", " ", text).strip()
