from collections import Counter

from config import CITY, MAX_EVENTS_TO_PRINT
from models import Event


def print_report(
    events: list[Event],
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
