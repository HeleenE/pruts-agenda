import os


def _env_or_default(name: str, default: str) -> str:
    return os.environ.get(name) or default


RADAR_API_URL = "https://radar.squat.net/api/1.2/search/events.json"
WAAG_ICS_URL = "https://waag.org/en/ics/feed.ics"
HACKERS_AND_DESIGNERS_ACTIVITIES_URL = (
    "https://hackersanddesigners.nl/activities"
)
THE_HMM_ICS_URL = "https://thehmm.nl/events-page/?ical=1"

CITY = "Amsterdam"
REQUEST_TIMEOUT = 60
REQUEST_HEADERS = {
    "User-Agent": (
        "PrutsAgenda/1.0 "
        "(https://github.com/HeleenE/pruts-agenda; personal calendar sync)"
    ),
    "Accept": "application/json,text/calendar,text/html;q=0.9,*/*;q=0.8",
}

MAX_EVENTS_TO_PRINT = 100

DEFAULT_GOOGLE_CALENDAR_ID = (
    "5700514223feffc197c9ac100226a547a3b02716f4a52acdeeacf07313423f88"
    "@group.calendar.google.com"
)
GOOGLE_CALENDAR_ID = _env_or_default(
    "GOOGLE_CALENDAR_ID",
    DEFAULT_GOOGLE_CALENDAR_ID,
)
GOOGLE_CREDENTIALS_FILE = os.environ.get(
    "GOOGLE_CREDENTIALS_FILE",
    "credentials.json",
)
GOOGLE_TOKEN_FILE = os.environ.get("GOOGLE_TOKEN_FILE", "token.json")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")
GOOGLE_TOKEN_JSON = os.environ.get("GOOGLE_TOKEN_JSON")
GOOGLE_CREDENTIALS_B64 = os.environ.get("GOOGLE_CREDENTIALS_B64")
GOOGLE_TOKEN_B64 = os.environ.get("GOOGLE_TOKEN_B64")

DEFAULT_EVENT_DURATION_HOURS = 2
