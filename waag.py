import json
import re
from html.parser import HTMLParser

import requests

from config import REQUEST_HEADERS, REQUEST_TIMEOUT, WAAG_ICS_URL
from ics import extract_event_blocks, parse_datetime, split_values
from models import Event


class WaagClient:
    def __init__(
        self,
        feed_url: str = WAAG_ICS_URL,
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        self.feed_url = feed_url
        self.timeout = timeout
        self._location_cache: dict[str, str] = {}

    def get_events(self) -> list[Event]:
        response = requests.get(
            self.feed_url,
            headers=REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()

        events = []
        for raw_event in extract_event_blocks(response.text):
            try:
                events.append(self._parse_event(raw_event))
            except (KeyError, TypeError, ValueError) as error:
                title = raw_event.get("SUMMARY", "Unknown event")
                print(f"Skipping malformed Waag event ({title}): {error}")

        return events

    def _parse_event(self, raw_event: dict[str, str]) -> Event:
        uid = raw_event["UID"]
        start = parse_datetime(raw_event["DTSTART"], raw_event.get("DTSTART_TZID"))
        end = (
            parse_datetime(raw_event["DTEND"], raw_event.get("DTEND_TZID"))
            if raw_event.get("DTEND")
            else None
        )
        all_day = (
            raw_event.get("DTSTART_VALUE") == "DATE"
            or "T" not in raw_event["DTSTART"]
        )
        title = raw_event.get("SUMMARY") or "Untitled Waag event"
        url = raw_event.get("URL", "")
        description = raw_event.get("DESCRIPTION", "")
        location = self._event_page_location(url) or raw_event.get("LOCATION", "")
        categories = split_values(raw_event.get("CATEGORIES"))

        return Event(
            radar_id=f"waag:{uid}",
            uuid=f"waag:{uid}",
            title=title,
            start=start,
            end=end,
            url=url,
            description=description,
            location=location,
            categories=categories,
            topics=["Waag"],
            source="waag",
            all_day=all_day,
        )

    def _event_page_location(self, url: str) -> str:
        if not url:
            return ""
        if url in self._location_cache:
            return self._location_cache[url]

        try:
            response = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=self.timeout,
            )
            response.raise_for_status()
            location = _extract_location_from_page(response.text)
        except requests.RequestException as error:
            print(f"Could not fetch Waag event location ({url}): {error}")
            location = ""
        except (AttributeError, TypeError, ValueError) as error:
            print(f"Could not parse Waag event location ({url}): {error}")
            location = ""

        self._location_cache[url] = location
        return location


def _extract_location_from_page(html: str) -> str:
    next_data = _NextDataParser()
    next_data.feed(html)
    if not next_data.data:
        return ""

    try:
        page_data = json.loads(next_data.data)
    except json.JSONDecodeError:
        return ""

    props = page_data.get("props") or {}
    page_props = props.get("pageProps") or {}
    node = page_props.get("node") or {}
    event_location = node.get("event_location") or {}
    location_body = event_location.get("body", "")
    if not location_body:
        return ""

    return _first_paragraph_text(location_body)


def _first_paragraph_text(html: str) -> str:
    parser = _FirstParagraphParser()
    parser.feed(html)
    text = "".join(parser.parts).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*,", ",", text)
    return text.strip(" ,")


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_next_data = False
        self.data = ""

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "script":
            return
        attributes = dict(attrs)
        self._in_next_data = attributes.get("id") == "__NEXT_DATA__"

    def handle_data(self, data: str) -> None:
        if self._in_next_data:
            self.data += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_next_data = False


class _FirstParagraphParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_paragraph = False
        self._done = False
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if self._done:
            return
        if tag == "p" and not self._in_paragraph:
            self._in_paragraph = True
            return
        if tag == "br" and self._in_paragraph:
            self.parts.append(", ")

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self._in_paragraph and not self._done:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._in_paragraph:
            self._in_paragraph = False
            self._done = True
