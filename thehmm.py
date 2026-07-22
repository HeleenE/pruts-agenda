import requests

from config import REQUEST_TIMEOUT, THE_HMM_ICS_URL
from ics import extract_event_blocks, parse_datetime, split_values
from models import Event


class TheHmmClient:
    def __init__(
        self,
        feed_url: str = THE_HMM_ICS_URL,
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        self.feed_url = feed_url
        self.timeout = timeout

    def get_events(self) -> list[Event]:
        response = requests.get(self.feed_url, timeout=self.timeout)
        response.raise_for_status()

        events = []
        for raw_event in extract_event_blocks(response.text):
            try:
                events.append(self._parse_event(raw_event))
            except (KeyError, TypeError, ValueError) as error:
                title = raw_event.get("SUMMARY", "Unknown event")
                print(f"Skipping malformed The Hmm event ({title}): {error}")

        return events

    def _parse_event(self, raw_event: dict[str, str]) -> Event:
        uid = raw_event["UID"]
        start = parse_datetime(raw_event["DTSTART"], raw_event.get("DTSTART_TZID"))
        end = (
            parse_datetime(raw_event["DTEND"], raw_event.get("DTEND_TZID"))
            if raw_event.get("DTEND")
            else None
        )
        title = raw_event.get("SUMMARY") or "Untitled The Hmm event"
        url = raw_event.get("URL", "")
        description = raw_event.get("DESCRIPTION", "")
        location = raw_event.get("LOCATION", "")
        categories = split_values(raw_event.get("CATEGORIES"))

        return Event(
            radar_id=f"thehmm:{uid}",
            uuid=f"thehmm:{uid}",
            title=title,
            start=start,
            end=end,
            url=url,
            description=description,
            location=location,
            categories=categories,
            topics=["The Hmm"],
            source="thehmm",
        )
