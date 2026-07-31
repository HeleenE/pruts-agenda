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

    sync_parser = subparsers.add_parser(
        "sync",
        help="Sync matching events to Google Calendar.",
    )
    sync_parser.add_argument(
        "--keep-stale",
        action="store_true",
        help=(
            "Keep future Google Calendar events previously synced by this "
            "tool even if they no longer match the current filters."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    from event_collection import collect_events
    from report import print_report

    collection = collect_events()

    if args.command in (None, "report"):
        print_report(
            collection.events,
            collection.skipped_venues,
            collection.skipped_categories,
        )
        return

    if args.command == "sync":
        from calendar_sync import GoogleCalendarSync
        from digest import append_sync_digest

        result = GoogleCalendarSync().sync_events(
            collection.events,
            delete_stale=not args.keep_stale,
        )
        digest_written = append_sync_digest(result)

        print(
            f"\nGoogle Calendar sync complete: "
            f"{result.created} created, "
            f"{result.updated} updated, "
            f"{result.deleted} deleted."
        )
        if digest_written:
            print("Sync digest updated.")
        else:
            print("Sync digest unchanged.")


if __name__ == "__main__":
    main()
