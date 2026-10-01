"""Recover previously published events when a source is unavailable."""

from urllib.parse import urlparse

from deleted_events import is_deleted_event, load_deleted_event_ids
from ics import extract_event_blocks, parse_datetime, split_values
from models import Event


SOURCES = {
    "Radar": ("radar", "radar.squat.net"),
    "Waag": ("waag", "waag.org"),
    "Hackers & Designers": ("hackersanddesigners", "hackersanddesigners.nl"),
    "The Hmm": ("thehmm", "thehmm.nl"),
    "Critical Infrastructure Lab": ("criticalinfralab", "criticalinfralab.net"),
}


def restore_failed_sources(feed: str, failed_sources: list[str]) -> list[Event]:
    failed = {SOURCES[name][0] for name in failed_sources}
    deleted_ids = load_deleted_event_ids()
    events = []
    for block in extract_event_blocks(feed):
        source = block.get("X-PRUTS-SOURCE")
        if not source:
            # Feeds published before source metadata was added use source URLs.
            host = (urlparse(block.get("URL", "")).hostname or "").removeprefix("www.")
            source = next((key for key, domain in SOURCES.values() if host == domain), None)
        if source not in failed:
            continue
        event = Event(
            radar_id=block.get("X-PRUTS-RADAR-ID", ""),
            uuid=block.get("X-PRUTS-UUID", block["UID"]),
            title=block.get("SUMMARY", ""),
            start=parse_datetime(block["DTSTART"], block.get("DTSTART_TZID")),
            end=parse_datetime(block["DTEND"], block.get("DTEND_TZID")) if block.get("DTEND") else None,
            url=block.get("URL", ""),
            description=block.get("DESCRIPTION", ""),
            location=block.get("LOCATION", ""),
            categories=split_values(block.get("CATEGORIES")),
            source=source,
            all_day=block.get("DTSTART_VALUE") == "DATE",
            calendar_uid=block["UID"],
            previous_occurrence_id=block.get("X-PRUTS-OCCURRENCE-ID", ""),
        )
        if event.is_upcoming and not is_deleted_event(event, deleted_ids):
            events.append(event)
    return events
