from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from calendar_sync import DeletedEvent, SyncResult, UpdatedEvent
from config import SYNC_DIGEST_FILE
from models import Event


LOCAL_TIMEZONE = ZoneInfo("Europe/Amsterdam")


def append_sync_digest(
    result: SyncResult,
    digest_file: str = SYNC_DIGEST_FILE,
) -> bool:
    if not result.has_changes:
        return False

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
            f"{result.created} new, "
            f"{result.updated} updated, "
            f"{result.deleted} deleted."
        ),
        "",
    ]

    _append_events(entry_lines, "New events", result.created_events)
    _append_updated_events(entry_lines, "Updated events", result.updated_events)
    _append_deleted_events(entry_lines, "Deleted events", result.deleted_events)

    entry = "\n".join(entry_lines).rstrip()

    if needs_heading:
        contents = "\n".join(lines).rstrip()
        path.write_text(f"{contents}\n\n{entry}\n", encoding="utf-8")
    else:
        existing = path.read_text(encoding="utf-8").rstrip()
        heading = "# Pruts Agenda Sync Digest"

        if existing.startswith(heading):
            rest = existing[len(heading):].strip()
            contents = f"{heading}\n\n{entry}"
            if rest:
                contents = f"{contents}\n\n{rest}"
            path.write_text(f"{contents}\n", encoding="utf-8")
        else:
            path.write_text(f"{entry}\n\n{existing}\n", encoding="utf-8")

    return True


def _append_events(lines: list[str], heading: str, events: list[Event]) -> None:
    if not events:
        return

    lines.extend([f"### {heading}", ""])

    for event in events:
        lines.append(f"- **{event.title}**")
        lines.append(f"  - When: {_format_datetime(event.start)}")

        if event.location:
            lines.append(f"  - Where: {event.location}")

        if event.source:
            lines.append(f"  - Source: {event.source}")

        if event.url:
            lines.append(f"  - Link: {event.url}")

    lines.append("")


def _append_updated_events(
    lines: list[str],
    heading: str,
    events: list[UpdatedEvent],
) -> None:
    if not events:
        return

    lines.extend([f"### {heading}", ""])

    for updated_event in events:
        event = updated_event.event
        lines.append(f"- **{event.title}**")
        lines.append("  - Changed:")
        for change in updated_event.changes:
            before = _format_change(change.label, change.before)
            after = _format_change(change.label, change.after)
            lines.append(f"    - {change.label}: {before} -> {after}")

        if event.url:
            lines.append(f"  - Link: {event.url}")

    lines.append("")


def _append_deleted_events(
    lines: list[str],
    heading: str,
    events: list[DeletedEvent],
) -> None:
    if not events:
        return

    lines.extend([f"### {heading}", ""])

    for event in events:
        lines.append(f"- **{event.title}**")

        if event.start:
            lines.append(f"  - When: {_format_datetime_string(event.start)}")

        if event.location:
            lines.append(f"  - Where: {event.location}")

        if event.source:
            lines.append(f"  - Source: {event.source}")

        if event.url:
            lines.append(f"  - Link: {event.url}")

    lines.append("")


def _format_datetime(value: datetime) -> str:
    return value.astimezone(LOCAL_TIMEZONE).strftime("%a %d %b %Y, %H:%M")


def _format_datetime_string(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value

    return _format_datetime(parsed)


def _format_change(label: str, value: str) -> str:
    if label in {"Start", "End"} and value:
        return _format_datetime_string(value)

    return _format_change_value(value)


def _format_change_value(value: str) -> str:
    if not value:
        return "(empty)"

    value = " ".join(value.split())

    if len(value) > 140:
        return f"{value[:137]}..."

    return value
