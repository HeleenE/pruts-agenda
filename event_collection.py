from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from sys import stderr

import requests

from config import CITY
from filters import should_include
from hackersanddesigners import HackersAndDesignersClient
from models import Event
from radar import RadarClient
from thehmm import TheHmmClient
from waag import WaagClient


@dataclass(frozen=True)
class EventCollection:
    events: list[Event]
    skipped_venues: Counter
    skipped_categories: Counter


def collect_events(city: str = CITY) -> EventCollection:
    radar = RadarClient()
    waag = WaagClient()
    hackers_and_designers = HackersAndDesignersClient()
    the_hmm = TheHmmClient()

    skipped_venues = Counter()
    skipped_categories = Counter()
    events = []

    source_events = [
        *get_source_events("Radar", lambda: radar.get_events(city)),
        *get_source_events("Waag", waag.get_events),
        *get_source_events(
            "Hackers & Designers",
            hackers_and_designers.get_events,
        ),
        *get_source_events("The Hmm", the_hmm.get_events),
    ]

    for event in source_events:
        if not event.is_upcoming:
            continue

        if should_include(event):
            events.append(event)
        else:
            if event.location:
                skipped_venues[event.location] += 1

            for category in event.categories:
                skipped_categories[category] += 1

    events.sort(key=lambda event: event.start)
    return EventCollection(events, skipped_venues, skipped_categories)


def get_source_events(name: str, fetch: Callable[[], list[Event]]) -> list[Event]:
    try:
        return fetch()
    except requests.RequestException as error:
        print(f"Skipping {name}: {error}", file=stderr)
        return []
