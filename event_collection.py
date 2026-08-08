from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from sys import stderr

import requests

from config import CITY
from critical_infra_lab import CriticalInfraLabClient
from deleted_events import is_deleted_event, load_deleted_event_ids
from filters import should_include
from hackersanddesigners import HackersAndDesignersClient
from manual_events import load_manual_events
from models import Event
from pakhuis_de_zwijger import PakhuisDeZwijgerClient
from radar import RadarClient
from thehmm import TheHmmClient
from waag import WaagClient


@dataclass(frozen=True)
class EventCollection:
    events: list[Event]
    skipped_venues: Counter
    skipped_categories: Counter
    failed_sources: list[str]


def collect_events(
    city: str = CITY,
) -> EventCollection:
    radar = RadarClient()
    waag = WaagClient()
    hackers_and_designers = HackersAndDesignersClient()
    the_hmm = TheHmmClient()
    critical_infra_lab = CriticalInfraLabClient()
    pakhuis_de_zwijger = PakhuisDeZwijgerClient()

    skipped_venues = Counter()
    skipped_categories = Counter()
    events = []
    failed_sources = []

    deleted_event_ids = load_deleted_event_ids()
    manual_events = load_manual_events()
    sources = [
        ("Radar", lambda: radar.get_events(city)),
        ("Waag", waag.get_events),
        ("Hackers & Designers", hackers_and_designers.get_events),
        ("The Hmm", the_hmm.get_events),
        ("Critical Infrastructure Lab", critical_infra_lab.get_events),
        ("Pakhuis de Zwijger", pakhuis_de_zwijger.get_events),
    ]
    source_events = []
    for name, fetch in sources:
        fetched_events = get_source_events(name, fetch)
        if fetched_events is None:
            failed_sources.append(name)
        else:
            source_events.extend(fetched_events)

    for event in source_events:
        if not event.is_upcoming:
            continue

        if is_deleted_event(event, deleted_event_ids):
            continue

        if _is_default_deleted_event(event):
            continue

        if should_include(event):
            events.append(event)
        else:
            if event.location:
                skipped_venues[event.location] += 1

            for category in event.categories:
                skipped_categories[category] += 1

    events.extend(
        event
        for event in manual_events
        if event.is_upcoming and not is_deleted_event(event, deleted_event_ids)
    )
    events.sort(key=lambda event: event.start)
    return EventCollection(events, skipped_venues, skipped_categories, failed_sources)


def get_source_events(
    name: str,
    fetch: Callable[[], list[Event]],
) -> list[Event] | None:
    try:
        return fetch()
    except requests.RequestException as error:
        print(f"Skipping {name}: {error}", file=stderr)
        return None


def _is_default_deleted_event(event: Event) -> bool:
    return event.source == "waag" and _is_multi_day_event(event)


def _is_multi_day_event(event: Event) -> bool:
    if not event.end:
        return False

    if event.all_day:
        return (event.end.date() - event.start.date()).days > 1

    return event.end.date() > event.start.date()
