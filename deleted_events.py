from pathlib import Path

import yaml

from config import DELETED_EVENTS_FILE
from models import Event


def load_deleted_event_ids(path: str = DELETED_EVENTS_FILE) -> set[str]:
    deleted_events_file = Path(path)
    if not deleted_events_file.exists():
        return set()

    data = yaml.safe_load(deleted_events_file.read_text(encoding="utf-8")) or {}
    event_ids = data.get("events", [])
    if not isinstance(event_ids, list):
        raise ValueError(f"{deleted_events_file} must contain an events list.")

    return {str(event_id) for event_id in event_ids if event_id}


def is_deleted_event(event: Event, deleted_event_ids: set[str]) -> bool:
    return any(
        event_id in deleted_event_ids
        for event_id in (
            event.uuid,
            event.radar_id,
            event.occurrence_id,
        )
    )
