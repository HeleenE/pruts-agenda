import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Pruts-worthy Amsterdam events from Radar.",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        metavar="command",
    )

    subparsers.add_parser(
        "report",
        help="Print matching events and skipped-item counts.",
    )

    subparsers.add_parser(
        "export-ics",
        help="Write matching events to an iCalendar feed file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    from event_collection import collect_events

    if args.command in (None, "report"):
        from report import print_report

        collection = collect_events()
        print_report(
            collection.events,
            collection.skipped_venues,
            collection.skipped_categories,
        )
        if collection.failed_sources:
            print(f"\nFailed sources: {', '.join(collection.failed_sources)}")
        return

    if args.command == "export-ics":
        from feed_digest import (
            append_feed_digest,
            build_feed_digest,
            read_existing_feed,
        )
        from html_export import write_html_page
        from ical_export import write_ical_feed
        from rss_export import write_rss_feed

        old_feed = read_existing_feed()
        collection = collect_events()
        if collection.failed_sources:
            print(f"Failed sources: {', '.join(collection.failed_sources)}")
            print("Keeping existing generated feeds unchanged.")
            digest = build_feed_digest(old_feed, [], collection.failed_sources)
            if append_feed_digest(digest):
                print("Sync digest updated.")
            return

        digest = build_feed_digest(old_feed, collection.events)
        path = write_ical_feed(collection.events)
        rss_path = write_rss_feed(collection.events)
        html_path = write_html_page(collection.events)
        print(f"Wrote {len(collection.events)} events to {path}.")
        print(f"Wrote RSS feed to {rss_path}.")
        print(f"Wrote website to {html_path}.")
        if append_feed_digest(digest):
            print("Sync digest updated.")
        else:
            print("Sync digest unchanged.")


if __name__ == "__main__":
    main()
