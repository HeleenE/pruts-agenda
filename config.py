import os


RADAR_API_URL = "https://radar.squat.net/api/1.2/search/events.json"
WAAG_ICS_URL = "https://waag.org/en/ics/feed.ics"
HACKERS_AND_DESIGNERS_ACTIVITIES_URL = (
    "https://hackersanddesigners.nl/activities"
)
THE_HMM_ICS_URL = "https://thehmm.nl/events-page/?ical=1"
CRITICAL_INFRA_LAB_URL = "https://www.criticalinfralab.net/"
PAKHUIS_DE_ZWIJGER_TECHNOLOGY_URL = (
    "https://dezwijger.nl/ajax/agenda/getItems"
)

CITY = "Amsterdam"
REQUEST_TIMEOUT = 60
REQUEST_HEADERS = {
    "User-Agent": (
        "PrutsAgenda/1.0 "
        "(https://github.com/HeleenE/pruts-agenda; iCalendar feed)"
    ),
    "Accept": "application/json,text/calendar,text/html;q=0.9,*/*;q=0.8",
}

MAX_EVENTS_TO_PRINT = 100
ICAL_OUTPUT_FILE = os.environ.get("ICAL_OUTPUT_FILE", "public/pruts-agenda.ics")
ICAL_CALENDAR_NAME = os.environ.get("ICAL_CALENDAR_NAME", "Pruts Agenda")
ICAL_UID_DOMAIN = os.environ.get("ICAL_UID_DOMAIN", "pruts-agenda.local")
RSS_OUTPUT_FILE = os.environ.get("RSS_OUTPUT_FILE", "public/feed.xml")
HTML_OUTPUT_FILE = os.environ.get("HTML_OUTPUT_FILE", "public/index.html")
HTML_TEMPLATE_FILE = os.environ.get("HTML_TEMPLATE_FILE", "templates/index.html")
PUBLIC_SITE_URL = os.environ.get(
    "PUBLIC_SITE_URL",
    "https://heleene.github.io/pruts-agenda/",
)
MANUAL_EVENTS_FILE = os.environ.get("MANUAL_EVENTS_FILE", "manual_events.yml")
DELETED_EVENTS_FILE = os.environ.get("DELETED_EVENTS_FILE", "deleted_events.yml")
SYNC_DIGEST_FILE = os.environ.get("SYNC_DIGEST_FILE", "SYNC_DIGEST.md")

DEFAULT_EVENT_DURATION_HOURS = 2
