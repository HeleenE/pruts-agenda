from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from config import ICAL_CALENDAR_NAME, ICAL_OUTPUT_FILE, ICAL_UID_DOMAIN
from models import Event


def build_ical_feed(events: list[Event]) -> str:
    return "\r\n".join(_fold_lines(_feed_lines(events))) + "\r\n"


def write_ical_feed(
    events: list[Event],
    output_file: str = ICAL_OUTPUT_FILE,
) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_ical_feed(events), encoding="utf-8")
    return path


def _feed_lines(events: list[Event]) -> list[str]:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Pruts Agenda//Events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _property("X-WR-CALNAME", ICAL_CALENDAR_NAME),
        "X-WR-TIMEZONE:Europe/Amsterdam",
    ]

    timestamp = _format_datetime(datetime.now(UTC))
    for event in sorted(events, key=lambda item: item.start):
        lines.extend(_event_lines(event, timestamp))

    lines.append("END:VCALENDAR")
    return lines


def _event_lines(event: Event, timestamp: str) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        _property("UID", f"{_uid_hash(event.occurrence_id)}@{ICAL_UID_DOMAIN}"),
        f"DTSTAMP:{timestamp}",
        _property("SUMMARY", event.title),
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
    ]

    lines.extend([
        format_event_start(event),
        format_event_end(event),
    ])

    if event.description:
        lines.append(_property("DESCRIPTION", event.description))
    if event.location:
        lines.append(_property("LOCATION", event.location))
    if event.url:
        lines.append(_property("URL", event.url))

    tags = [*event.categories, *event.topics]
    if tags:
        lines.append(_property("CATEGORIES", ",".join(tags)))

    lines.append("END:VEVENT")
    return lines


def _uid_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def format_event_start(event: Event) -> str:
    if event.all_day:
        return f"DTSTART;VALUE=DATE:{_format_date(event.start)}"

    return f"DTSTART:{_format_datetime(event.start)}"


def format_event_end(event: Event) -> str:
    if event.all_day:
        return f"DTEND;VALUE=DATE:{_format_date(event.end_or_default)}"

    return f"DTEND:{_format_datetime(event.end_or_default)}"


def _format_date(value: datetime) -> str:
    return value.date().strftime("%Y%m%d")


def _property(name: str, value: str) -> str:
    return f"{name}:{_escape_text(value)}"


def _escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _fold_lines(lines: list[str]) -> list[str]:
    folded = []
    for line in lines:
        folded.extend(_fold_line(line))
    return folded


def _fold_line(line: str) -> list[str]:
    if len(line.encode("utf-8")) <= 75:
        return [line]

    chunks = []
    current = ""
    byte_limit = 75
    for char in line:
        next_value = f"{current}{char}"
        if len(next_value.encode("utf-8")) > byte_limit:
            chunks.append(current)
            current = char
            byte_limit = 74
        else:
            current = next_value

    if current:
        chunks.append(current)

    return [chunks[0], *[f" {chunk}" for chunk in chunks[1:]]]
