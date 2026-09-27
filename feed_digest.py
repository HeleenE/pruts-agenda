from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import ICAL_OUTPUT_FILE, SYNC_DIGEST_FILE
from dates import LOCAL_TIMEZONE, format_local_datetime
from ics import extract_event_blocks, parse_datetime
from ical_export import format_event_end, format_event_start
from models import Event


@dataclass(frozen=True)
class FeedEvent:
    uid: str
    title: str
    start: datetime
    end: datetime | None
    all_day: bool
    compare_start: str
    compare_end: str
    location: str
    url: str


@dataclass(frozen=True)
class FieldChange:
    label: str
    old: str
    new: str


@dataclass(frozen=True)
class FeedChange:
    event: FeedEvent
    changes: list[FieldChange]


@dataclass(frozen=True)
class FeedDigest:
    added: list[FeedEvent]
    outdated: list[FeedEvent]
    removed: list[FeedEvent]
    changed: list[FeedChange]
    failed_sources: list[str]


def build_feed_digest(
    old_feed: str,
    new_events: list[Event],
    failed_sources: list[str] | None = None,
    now: datetime | None = None,
) -> FeedDigest:
    sync_time = now or datetime.now(LOCAL_TIMEZONE)
    old_events = _parse_feed_events(old_feed)
    new_events_by_uid = {
        _event_uid(event): _to_feed_event(event)
        for event in new_events
    }

    added = [
        event
        for uid, event in new_events_by_uid.items()
        if uid not in old_events
    ]
    missing = []
    if not failed_sources:
        missing = [
            event
            for uid, event in old_events.items()
            if uid not in new_events_by_uid
        ]
    outdated = [event for event in missing if _event_has_ended(event, sync_time)]
    removed = [event for event in missing if not _event_has_ended(event, sync_time)]
    changed = []
    for uid, event in new_events_by_uid.items():
        if uid not in old_events:
            continue

        change = _event_change(old_events[uid], event)
        if change:
            changed.append(change)

    return FeedDigest(
        added=sorted(added, key=lambda event: event.start),
        outdated=sorted(outdated, key=lambda event: event.start),
        removed=sorted(removed, key=lambda event: event.start),
        changed=sorted(changed, key=lambda change: change.event.start),
        failed_sources=failed_sources or [],
    )


def append_feed_digest(
    digest: FeedDigest,
    digest_file: str = SYNC_DIGEST_FILE,
) -> bool:
    path = Path(digest_file)
    needs_heading = not path.exists() or path.stat().st_size == 0
    lines = []

    if needs_heading:
        lines.extend([
            "# Pruts Agenda Sync Digest",
            "",
        ])

    entry_lines = [
        f"## {datetime.now(LOCAL_TIMEZONE).strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        (
            f"{len(digest.added)} new, "
            f"{len(digest.changed)} updated, "
            f"{len(digest.outdated)} outdated, "
            f"{len(digest.removed)} deleted."
        ),
        "",
    ]
    _append_events(entry_lines, "New events", digest.added)
    _append_changed_events(entry_lines, "Updated events", digest.changed)
    _append_events(entry_lines, "Outdated events", digest.outdated)
    _append_events(entry_lines, "Deleted events", digest.removed)
    _append_failed_sources(entry_lines, digest.failed_sources)

    entry = "\n".join(entry_lines).rstrip()
    if needs_heading:
        path.write_text("\n".join([*lines, entry]).rstrip() + "\n", encoding="utf-8")
    else:
        existing = path.read_text(encoding="utf-8").rstrip()
        heading = "# Pruts Agenda Sync Digest"
        if existing.splitlines()[0] == heading:
            rest = "\n".join(existing.splitlines()[1:]).strip()
            contents = f"{heading}\n\n{entry}"
            if rest:
                contents = f"{contents}\n\n{rest}"
            path.write_text(f"{contents}\n", encoding="utf-8")
        else:
            path.write_text(f"{entry}\n\n{existing}\n", encoding="utf-8")

    return True


def read_existing_feed(path: str = ICAL_OUTPUT_FILE) -> str:
    feed_path = Path(path)
    if not feed_path.exists():
        return ""
    return feed_path.read_text(encoding="utf-8")


def _append_events(lines: list[str], heading: str, events: list[FeedEvent]) -> None:
    if not events:
        return

    lines.extend([f"### {heading}", ""])
    for event in events:
        lines.append(_event_line(event))
    lines.append("")


def _append_changed_events(
    lines: list[str],
    heading: str,
    changes: list[FeedChange],
) -> None:
    if not changes:
        return

    lines.extend([f"### {heading}", ""])
    for change in changes:
        lines.append(_event_line(change.event))
        for field in change.changes:
            lines.append(
                f"  - {field.label}: {_display_value(field.old)} → "
                f"{_display_value(field.new)}"
            )
    lines.append("")


def _append_failed_sources(lines: list[str], failed_sources: list[str]) -> None:
    if not failed_sources:
        return

    lines.extend(["### Source warnings", ""])
    lines.append(f"- Unavailable: {', '.join(failed_sources)}")
    lines.append("")


def _parse_feed_events(feed: str) -> dict[str, FeedEvent]:
    events = {}
    for block in extract_event_blocks(feed):
        start = _parse_feed_datetime(block, "DTSTART")
        end = _parse_feed_datetime(block, "DTEND", required=False)
        event = FeedEvent(
            uid=block.get("UID", ""),
            title=block.get("SUMMARY", ""),
            start=start,
            end=end,
            all_day=block.get("DTSTART_VALUE") == "DATE",
            compare_start=block.get("DTSTART_RAW", ""),
            compare_end=block.get("DTEND_RAW", ""),
            location=block.get("LOCATION", ""),
            url=block.get("URL", ""),
        )
        if event.uid:
            events[event.uid] = event
    return events


def _event_uid(event: Event) -> str:
    from ical_export import _uid_hash

    from config import ICAL_UID_DOMAIN

    return f"{_uid_hash(event.occurrence_id)}@{ICAL_UID_DOMAIN}"


def _to_feed_event(event: Event) -> FeedEvent:
    return FeedEvent(
        uid=_event_uid(event),
        title=event.title,
        start=event.start,
        end=event.end_or_default,
        all_day=event.all_day,
        compare_start=format_event_start(event),
        compare_end=format_event_end(event),
        location=event.location,
        url=event.url,
    )


def _event_change(old: FeedEvent, new: FeedEvent) -> FeedChange | None:
    changes = []
    if old.title != new.title:
        changes.append(FieldChange("title", old.title, new.title))
    if old.compare_start != new.compare_start:
        changes.append(
            FieldChange("when", _format_start(old), _format_start(new))
        )
    if old.compare_end != new.compare_end:
        changes.append(FieldChange("end", _format_end(old), _format_end(new)))
    if old.location != new.location:
        changes.append(FieldChange("where", old.location, new.location))
    if old.url != new.url:
        changes.append(FieldChange("url", old.url, new.url))

    if not changes:
        return None

    return FeedChange(new, changes)


def _parse_feed_datetime(
    block: dict[str, str],
    name: str,
    required: bool = True,
) -> datetime | None:
    value = block.get(name, "")
    if not value:
        if required:
            raise ValueError(f"Missing {name} in existing calendar event")
        return None
    if block.get(f"{name}_VALUE") == "DATE":
        return datetime.strptime(value, "%Y%m%d").replace(
            tzinfo=LOCAL_TIMEZONE,
        )
    return parse_datetime(value, block.get(f"{name}_TZID"))


def _event_has_ended(event: FeedEvent, now: datetime) -> bool:
    return (event.end or event.start) <= now


def _event_line(event: FeedEvent) -> str:
    parts = [f"- **{event.title}**", _format_start(event)]
    if event.location:
        parts.append(event.location)
    if event.url:
        parts.append(event.url)
    return " - ".join(parts)


def _format_start(event: FeedEvent) -> str:
    return _format_datetime(event.start, event.all_day)


def _format_end(event: FeedEvent) -> str:
    if event.end is None:
        return ""
    return _format_datetime(event.end, event.all_day)


def _format_datetime(value: datetime, all_day: bool) -> str:
    if all_day:
        return value.strftime("%a %d %b %Y")
    return format_local_datetime(value)


def _display_value(value: str) -> str:
    return value or "*(empty)*"
