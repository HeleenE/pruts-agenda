from datetime import datetime
from zoneinfo import ZoneInfo


LOCAL_TIMEZONE = ZoneInfo("Europe/Amsterdam")


def format_local_datetime(value: datetime) -> str:
    return value.astimezone(LOCAL_TIMEZONE).strftime("%a %d %b %Y, %H:%M")
