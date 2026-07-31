from datetime import datetime
from zoneinfo import ZoneInfo


LOCAL_TIMEZONE = ZoneInfo("Europe/Amsterdam")


def format_local_datetime(value: datetime) -> str:
    return value.astimezone(LOCAL_TIMEZONE).strftime("%a %d %b %Y, %H:%M")


def format_local_datetime_string(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value

    return format_local_datetime(parsed)
