from datetime import date, datetime
from pathlib import Path

import yaml

from config import MANUAL_EVENTS_FILE
from dates import LOCAL_TIMEZONE
from models import Event


PDZ_SECTION_START = "# BEGIN AUTO-IMPORTED PAKHUIS DE ZWIJGER EVENTS"
PDZ_SECTION_END = "# END AUTO-IMPORTED PAKHUIS DE ZWIJGER EVENTS"


def load_manual_events(path: str = MANUAL_EVENTS_FILE) -> list[Event]:
    manual_events_file = Path(path)
    if not manual_events_file.exists():
        return []

    data = yaml.safe_load(manual_events_file.read_text(encoding="utf-8")) or {}
    events = data.get("events", [])
    if not isinstance(events, list):
        raise ValueError(f"{manual_events_file} must contain an events list.")

    return [_to_event(item, manual_events_file) for item in events]


def update_pakhuis_manual_events(
    events: list[Event],
    path: str = MANUAL_EVENTS_FILE,
) -> int:
    manual_events_file = Path(path)
    text = manual_events_file.read_text(encoding="utf-8")
    base_text = _without_managed_pdz_section(text)
    data = yaml.safe_load(base_text) or {}
    existing_urls = {
        str(item.get("url", ""))
        for item in data.get("events", [])
        if isinstance(item, dict)
    }
    imported = [event for event in events if event.url not in existing_urls]
    section = _format_managed_pdz_section(imported)
    updated = f"{base_text.rstrip()}\n\n{section}\n"
    manual_events_file.write_text(updated, encoding="utf-8")
    return len(imported)


def _without_managed_pdz_section(text: str) -> str:
    start = text.find(PDZ_SECTION_START)
    end = text.find(PDZ_SECTION_END)
    if start < 0 and end < 0:
        return text
    if start < 0 or end < start:
        raise ValueError("Incomplete auto-imported PdZ section in manual_events.yml.")
    end += len(PDZ_SECTION_END)
    return f"{text[:start].rstrip()}\n{text[end:].lstrip()}"


def _format_managed_pdz_section(events: list[Event]) -> str:
    items = [_pakhuis_event_mapping(event) for event in events]
    dumped = yaml.safe_dump(
        {"events": items},
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    )
    event_lines = [f"  {line}" for line in dumped.splitlines()[1:]]
    return "\n".join([PDZ_SECTION_START, *event_lines, PDZ_SECTION_END])


def _pakhuis_event_mapping(event: Event) -> dict:
    slug = event.radar_id.removeprefix("pakhuisdezwijger:")
    item = {
        "id": f"pdz-{slug}",
        "title": event.title,
        "start": event.start.strftime("%Y-%m-%d %H:%M"),
    }
    if event.end:
        item["end"] = event.end.strftime("%Y-%m-%d %H:%M")
    if event.all_day:
        item["all_day"] = True
    if event.location:
        item["location"] = event.location
    if event.url:
        item["url"] = event.url
    if event.description:
        item["description"] = event.description
    item["source"] = "Pakhuis de Zwijger"
    return item


def _to_event(item: dict, manual_events_file: Path) -> Event:
    if not isinstance(item, dict):
        raise ValueError(f"Each event in {manual_events_file} must be a mapping.")

    event_id = _required_text(item, "id", manual_events_file)
    title = _required_text(item, "title", manual_events_file)
    start = _required_datetime(item, "start", manual_events_file)
    end = _optional_datetime(item, "end", manual_events_file)
    all_day = bool(item.get("all_day", False))

    return Event(
        radar_id=event_id,
        uuid=f"manual:{event_id}",
        title=title,
        start=start,
        end=end,
        url=str(item.get("url", "") or ""),
        description=str(item.get("description", "") or ""),
        location=str(item.get("location", "") or ""),
        categories=_text_list(item.get("categories", []), manual_events_file),
        topics=_text_list(item.get("topics", []), manual_events_file),
        source=str(item.get("source", "") or ""),
        all_day=all_day,
    )


def _required_text(item: dict, name: str, manual_events_file: Path) -> str:
    value = item.get(name)
    if not value:
        raise ValueError(f"Missing {name!r} in {manual_events_file}.")
    return str(value)


def _required_datetime(
    item: dict,
    name: str,
    manual_events_file: Path,
) -> datetime:
    value = item.get(name)
    if not value:
        raise ValueError(f"Missing {name!r} in {manual_events_file}.")
    return _parse_datetime(value, manual_events_file)


def _optional_datetime(
    item: dict,
    name: str,
    manual_events_file: Path,
) -> datetime | None:
    value = item.get(name)
    if not value:
        return None
    return _parse_datetime(value, manual_events_file)


def _parse_datetime(value: object, manual_events_file: Path) -> datetime:
    if isinstance(value, datetime):
        return _with_timezone(value)

    if isinstance(value, date):
        return datetime.combine(
            value,
            datetime.min.time(),
            tzinfo=LOCAL_TIMEZONE,
        )

    if not isinstance(value, str):
        raise ValueError(f"Unsupported date value {value!r} in {manual_events_file}.")

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            f"Could not parse date value {value!r} in {manual_events_file}."
        ) from error

    return _with_timezone(parsed)


def _with_timezone(value: datetime) -> datetime:
    if value.tzinfo:
        return value
    return value.replace(tzinfo=LOCAL_TIMEZONE)


def _text_list(value: object, manual_events_file: Path) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise ValueError(f"Expected a list in {manual_events_file}, got {value!r}.")

    return [str(item) for item in value]
