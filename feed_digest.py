from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import ICAL_OUTPUT_FILE, SYNC_DIGEST_FILE
from dates import LOCAL_TIMEZONE, format_local_datetime
from ical_export import format_event_end, format_event_start
from models import Event


@dataclass(frozen=True)
class FeedEvent:
    uid: str
    title: str
    start: str
    end: str
    compare_start: str
    compare_end: str
    sort_key: str
    location: str
    url: str


@dataclass(frozen=True)
class FeedChange:
    title: str
    changes: list[str]


@dataclass(frozen=True)
class FeedDigest:
    added: list[FeedEvent]
    removed: list[FeedEvent]
    changed: list[FeedChange]
    failed_sources: list[str]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def build_feed_digest(
    old_feed: str,
    new_events: list[Event],
    failed_sources: list[str] | None = None,
) -> FeedDigest:
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
    removed = []
    if not failed_sources:
        removed = [
            event
            for uid, event in old_events.items()
            if uid not in new_events_by_uid
        ]
    changed = [
        _event_change(old_events[uid], event)
        for uid, event in new_events_by_uid.items()
        if uid in old_events and _event_change(old_events[uid], event)
    ]

    return FeedDigest(
        added=sorted(added, key=lambda event: event.sort_key),
        removed=sorted(removed, key=lambda event: event.sort_key),
        changed=sorted(changed, key=lambda change: change.title.lower()),
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
            f"{len(digest.removed)} deleted."
        ),
        "",
    ]
    _append_events(entry_lines, "New events", digest.added)
    _append_changed_events(entry_lines, "Updated events", digest.changed)
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
        parts = [f"- **{event.title}**", event.start]
        if event.location:
            parts.append(event.location)
        if event.url:
            parts.append(event.url)
        lines.append(" - ".join(parts))
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
        lines.append(f"- **{change.title}**: {', '.join(change.changes)}")
    lines.append("")


def _append_failed_sources(lines: list[str], failed_sources: list[str]) -> None:
    if not failed_sources:
        return

    lines.extend(["### Source warnings", ""])
    lines.append(f"- Unavailable: {', '.join(failed_sources)}")
    lines.append("")


def _parse_feed_events(feed: str) -> dict[str, FeedEvent]:
    events = {}
    for block in _event_blocks(feed):
        event = FeedEvent(
            uid=block.get("UID", ""),
            title=block.get("SUMMARY", ""),
            start=block.get("DTSTART", ""),
            end=block.get("DTEND", ""),
            compare_start=block.get("DTSTART_COMPARE", ""),
            compare_end=block.get("DTEND_COMPARE", ""),
            sort_key=_sort_key_from_ical_start(block.get("DTSTART_COMPARE", "")),
            location=block.get("LOCATION", ""),
            url=block.get("URL", ""),
        )
        if event.uid:
            events[event.uid] = event
    return events


def _event_blocks(feed: str) -> list[dict[str, str]]:
    blocks = []
    current: dict[str, str] | None = None

    for line in _unfold_lines(feed):
        if line == "BEGIN:VEVENT":
            current = {}
            continue

        if line == "END:VEVENT":
            if current is not None:
                blocks.append(current)
            current = None
            continue

        if current is None or ":" not in line:
            continue

        name, value = line.split(":", 1)
        property_name = name.split(";", 1)[0]
        current[property_name] = _unescape_text(value)
        if property_name in {"DTSTART", "DTEND"}:
            current[f"{property_name}_COMPARE"] = line

    return blocks


def _unfold_lines(feed: str) -> list[str]:
    unfolded = []
    for line in feed.splitlines():
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line.rstrip("\r"))
    return unfolded


def _event_uid(event: Event) -> str:
    from ical_export import _uid_hash

    from config import ICAL_UID_DOMAIN

    return f"{_uid_hash(event.occurrence_id)}@{ICAL_UID_DOMAIN}"


def _to_feed_event(event: Event) -> FeedEvent:
    return FeedEvent(
        uid=_event_uid(event),
        title=event.title,
        start=format_local_datetime(event.start),
        end=format_local_datetime(event.end_or_default),
        compare_start=format_event_start(event),
        compare_end=format_event_end(event),
        sort_key=event.start.astimezone(LOCAL_TIMEZONE).isoformat(),
        location=event.location,
        url=event.url,
    )


def _event_change(old: FeedEvent, new: FeedEvent) -> FeedChange | None:
    changes = []
    for field, label in (
        ("title", "title"),
        ("compare_start", "when"),
        ("compare_end", "end"),
        ("location", "where"),
        ("url", "url"),
    ):
        if getattr(old, field) != getattr(new, field):
            changes.append(label)

    if not changes:
        return None

    return FeedChange(new.title or old.title, changes)


def _sort_key_from_ical_start(value: str) -> str:
    if ":" not in value:
        return ""

    raw_value = value.split(":", 1)[1]
    if "T" in raw_value:
        return raw_value
    return f"{raw_value}T000000"


def _unescape_text(value: str) -> str:
    return (
        value.replace(r"\n", "\n")
        .replace(r"\N", "\n")
        .replace(r"\,", ",")
        .replace(r"\;", ";")
        .replace(r"\\", "\\")
    )
