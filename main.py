import argparse
from collections import Counter

from config import CITY, MAX_EVENTS_TO_PRINT
from filters import should_include
from hackersanddesigners import HackersAndDesignersClient
from radar import RadarClient
from thehmm import TheHmmClient
from waag import WaagClient


def collect_events() -> tuple[list, Counter, Counter]:
    radar = RadarClient()
    waag = WaagClient()
    hackers_and_designers = HackersAndDesignersClient()
    the_hmm = TheHmmClient()

    skipped_venues = Counter()
    skipped_categories = Counter()

    events = []

    source_events = [
        *radar.get_events(CITY),
        *waag.get_events(),
        *hackers_and_designers.get_events(),
        *the_hmm.get_events(),
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
    return events, skipped_venues, skipped_categories


def print_report(
    events: list,
    skipped_venues: Counter,
    skipped_categories: Counter,
) -> None:
    print(f"Found {len(events)} Pruts-worthy events in {CITY}\n")

    for event in events[:MAX_EVENTS_TO_PRINT]:
        print(event)
        print("-" * 80)

    print("\nSkipped venues")
    print("=" * 80)
    for venue, count in skipped_venues.most_common():
        print(f"{count:>3}  {venue}")

    print("\nSkipped categories")
    print("=" * 80)
    for category, count in skipped_categories.most_common():
        print(f"{count:>3}  {category}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Pruts-worthy Amsterdam events from Radar.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Create or update matching events in Google Calendar.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Do not print the event and skipped-item report.",
    )
    parser.add_argument(
        "--delete-stale",
        action="store_true",
        help=(
            "Delete future Google Calendar events previously synced by this "
            "tool if they no longer match the current filters."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events, skipped_venues, skipped_categories = collect_events()

    if not args.no_report:
        print_report(events, skipped_venues, skipped_categories)

    if args.sync:
        from calendar_sync import GoogleCalendarSync

        created, updated, deleted = GoogleCalendarSync().sync_events(
            events,
            delete_stale=args.delete_stale,
        )
        print(
            f"\nGoogle Calendar sync complete: "
            f"{created} created, {updated} updated, {deleted} deleted."
        )


if __name__ == "__main__":
    main()
