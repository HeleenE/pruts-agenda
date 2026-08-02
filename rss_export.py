from datetime import UTC, datetime
from email.utils import format_datetime
from hashlib import sha256
from pathlib import Path
from xml.sax.saxutils import escape

from config import ICAL_CALENDAR_NAME, PUBLIC_SITE_URL, RSS_OUTPUT_FILE
from models import Event


def build_rss_feed(events: list[Event]) -> str:
    now = datetime.now(UTC)
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<rss version="2.0">',
        "  <channel>",
        f"    <title>{_xml(ICAL_CALENDAR_NAME)}</title>",
        f"    <link>{_xml(PUBLIC_SITE_URL)}</link>",
        "    <description>Upcoming hacker, maker and critical technology events.</description>",
        f"    <lastBuildDate>{_rss_date(now)}</lastBuildDate>",
    ]

    for event in sorted(events, key=lambda item: item.start):
        lines.extend(_item_lines(event))

    lines.extend([
        "  </channel>",
        "</rss>",
    ])
    return "\n".join(lines) + "\n"


def write_rss_feed(
    events: list[Event],
    output_file: str = RSS_OUTPUT_FILE,
) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_rss_feed(events), encoding="utf-8")
    return path


def _item_lines(event: Event) -> list[str]:
    link = event.url or PUBLIC_SITE_URL
    description = _description(event)
    return [
        "    <item>",
        f"      <title>{_xml(event.title)}</title>",
        f"      <link>{_xml(link)}</link>",
        f"      <guid isPermaLink=\"false\">{_xml(_guid(event))}</guid>",
        f"      <pubDate>{_rss_pub_date(event)}</pubDate>",
        f"      <description>{_xml(description)}</description>",
        "    </item>",
    ]


def _description(event: Event) -> str:
    parts = [_event_time(event)]
    if event.location:
        parts.append(event.location)
    source = _source_label(event)
    if source:
        parts.append(source)
    if event.description:
        parts.append(_truncate(event.description, 280))
    return " - ".join(parts)


def _event_time(event: Event) -> str:
    if event.all_day:
        return event.start.strftime("%d %b %Y")
    return event.start.astimezone().strftime("%d %b %Y, %H:%M")


def _source_label(event: Event) -> str:
    if event.source == "manual":
        return ""
    labels = {
        "criticalinfralab": "Critical Infrastructure Lab",
        "hackersanddesigners": "Hackers & Designers",
        "radar": "Radar",
        "thehmm": "The Hmm",
        "waag": "Waag",
    }
    return labels.get(event.source, event.source)


def _guid(event: Event) -> str:
    digest = sha256(event.occurrence_id.encode("utf-8")).hexdigest()
    return f"pruts-agenda:{digest}"


def _rss_pub_date(event: Event) -> str:
    if event.all_day:
        value = event.start.replace(hour=12, minute=0, second=0, microsecond=0)
        return _rss_date(value)
    return _rss_date(event.start)


def _rss_date(value: datetime) -> str:
    return format_datetime(value.astimezone(UTC), usegmt=True)


def _truncate(value: str, max_length: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3].rstrip()}..."


def _xml(value: str) -> str:
    return escape(value, {"\"": "&quot;"})
