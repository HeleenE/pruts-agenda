from dataclasses import dataclass

from models import Event


@dataclass(frozen=True)
class DeletedEvent:
    title: str
    start: str
    location: str
    source: str
    url: str


@dataclass(frozen=True)
class EventChange:
    label: str
    before: str
    after: str


@dataclass(frozen=True)
class UpdatedEvent:
    event: Event
    changes: list[EventChange]


@dataclass(frozen=True)
class SyncResult:
    created_events: list[Event]
    updated_events: list[UpdatedEvent]
    deleted_events: list[DeletedEvent]

    @property
    def created(self) -> int:
        return len(self.created_events)

    @property
    def updated(self) -> int:
        return len(self.updated_events)

    @property
    def deleted(self) -> int:
        return len(self.deleted_events)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.created_events
            or self.updated_events
            or self.deleted_events
        )
