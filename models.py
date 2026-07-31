from dataclasses import dataclass, field
from datetime import datetime, timedelta

from config import DEFAULT_EVENT_DURATION_HOURS


@dataclass
class Event:
    radar_id: str
    uuid: str
    title: str
    start: datetime
    end: datetime | None
    url: str

    description: str = ""
    location: str = ""
    categories: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    source: str = "radar"

    @property
    def is_upcoming(self) -> bool:
        now = datetime.now().astimezone()

        # Keep currently running events too.
        final_time = self.end or self.start
        return final_time >= now

    @property
    def end_or_default(self) -> datetime:
        return self.end or self.start + timedelta(
            hours=DEFAULT_EVENT_DURATION_HOURS,
        )

    @property
    def occurrence_id(self) -> str:
        return f"{self.uuid}:{self.start.isoformat()}"

    @property
    def stable_id(self) -> str:
        return self.uuid
