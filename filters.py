import re

from models import Event

KEEP_CATEGORIES = {
    "work space/diy",
    "course/workshop",
    "discussion/presentation",
}

KEEP_VENUES = {
    "Technologia Incognita",
    "Internet Archive",
}

KEEP_SOURCES = {
    "hackersanddesigners",
    "thehmm",
    "waag",
}

SKIP_CATEGORIES = {
    "party",
    "music/concert",
    "food",
    "bar/cafe",
    "film",
    "action/protest/camp",
    "children's activity",
}

KEEP_TITLE_WORDS = {
    "hack",
    "hacker",
    "electronics",
    "pcb",
    "3d",
    "arduino",
    "microcontroller",
    "open source",
    "repair",
    "linux",
    "ai",
    "archive",
    "creative coding",
    "artificial intelligence",
    "tech",
}


def _has_title_keyword(title: str) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(word)}(?!\w)", title)
        for word in KEEP_TITLE_WORDS
    )


def should_include(event: Event) -> bool:
    title = event.title.lower()
    location = event.location.lower()

    # Always trust certain venues.
    if any(venue.lower() in location for venue in KEEP_VENUES):
        return True

    # Trust curated feeds that were added explicitly.
    if event.source in KEEP_SOURCES:
        return True

    # Interesting categories are too broad on their own; the title still needs
    # to show a Pruts-ish hook unless the venue is already trusted.
    if _has_title_keyword(title):
        return True

    # Purely social events.
    if event.categories and all(
        category in SKIP_CATEGORIES
        for category in event.categories
    ):
        return False

    return False
