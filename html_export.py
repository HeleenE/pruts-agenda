from datetime import timedelta
from html import escape
from pathlib import Path

from config import HTML_OUTPUT_FILE, HTML_TEMPLATE_FILE
from dates import LOCAL_TIMEZONE
from models import Event


SOURCE_LABELS = {
    "criticalinfralab": "Critical Infrastructure Lab",
    "hackersanddesigners": "Hackers & Designers",
    "radar": "Radar Squad",
    "thehmm": "The Hmm",
    "waag": "Waag",
}


def build_html_page(events: list[Event], template: str) -> str:
    ordered_events = sorted(events, key=lambda event: event.start)
    agenda = "\n".join(_event_html(event, index) for index, event in enumerate(ordered_events))
    if not agenda:
        agenda = '        <p class="empty">No upcoming events.</p>'

    minimum_date = ""
    if ordered_events:
        minimum_date = _local_date(ordered_events[0])

    return (
        template.replace("{{AGENDA}}", agenda)
        .replace("{{MIN_EVENT_DATE}}", escape(minimum_date, quote=True))
    )


def write_html_page(
    events: list[Event],
    template_file: str = HTML_TEMPLATE_FILE,
    output_file: str = HTML_OUTPUT_FILE,
) -> Path:
    template = Path(template_file).read_text(encoding="utf-8")
    page = build_html_page(events, template)
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path


def _event_html(event: Event, index: int) -> str:
    local_start = event.start.astimezone(LOCAL_TIMEZONE)
    classes = "event is-clickable" if event.url else "event"
    link_attributes = ""
    if event.url:
        link_attributes = f' data-url="{escape(event.url, quote=True)}"'

    title = escape(event.title)
    if event.url:
        title = f'<a href="{escape(event.url, quote=True)}">{title}</a>'

    description = _truncate(event.description, 240)
    description_html = ""
    if description:
        description_html = f'            <p class="event-description">{escape(description)}</p>\n'

    source = SOURCE_LABELS.get(event.source, "" if event.source == "manual" else event.source)
    source_names = {event.source.casefold(), source.casefold()}
    tags = [
        tag
        for tag in [*event.categories, *event.topics]
        if tag.casefold() not in source_names
    ]
    tags_html = "".join(
        f'<span class="tag">{escape(tag)}</span>' for tag in tags
    )
    if source:
        tags_html += f'<span class="event-source">{escape(source)}</span>'
    tags_block = ""
    if tags_html:
        tags_block = f'              <div class="event-tags">{tags_html}</div>\n'

    location_html = ""
    if event.location:
        location_html = f'              <p class="event-location">{escape(event.location)}</p>\n'

    return (
        f'        <article class="{classes}" id="event-{index}" '
        f'data-start="{_local_date(event)}"{link_attributes}>\n'
        f'          <time class="event-date" datetime="{escape(event.start.isoformat(), quote=True)}">\n'
        f'            <span>{local_start.strftime("%b")}</span>\n'
        f'            <span>{local_start.day:02d}</span>\n'
        "          </time>\n"
        "          <div class=\"event-body\">\n"
        "            <div class=\"event-topline\">\n"
        f"              <h2>{title}</h2>\n"
        "            </div>\n"
        f'            <p class="event-time">{escape(_event_time(event))}</p>\n'
        f"{description_html}"
        "            <div class=\"event-meta\">\n"
        f"{tags_block}"
        f"{location_html}"
        "            </div>\n"
        "          </div>\n"
        "        </article>"
    )


def _event_time(event: Event) -> str:
    start = event.start.astimezone(LOCAL_TIMEZONE)
    if not event.all_day:
        return f"{start.strftime('%a')} {start.day} {start.strftime('%b')}, {start:%H:%M}"

    start_text = f"{start.strftime('%a')} {start.day} {start.strftime('%b %Y')}"
    if not event.end:
        return start_text

    end = event.end.astimezone(LOCAL_TIMEZONE) - timedelta(days=1)
    if start.date() == end.date():
        return start_text
    end_text = f"{end.strftime('%a')} {end.day} {end.strftime('%b %Y')}"
    return f"{start_text} - {end_text}"


def _local_date(event: Event) -> str:
    return event.start.astimezone(LOCAL_TIMEZONE).date().isoformat()


def _truncate(value: str, max_length: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3].rstrip()}..."
