from datetime import datetime, timezone
from html import unescape
from typing import Any
from zoneinfo import ZoneInfo
import re


def extract_event_blocks(value: str) -> list[dict[str, str]]:
    lines = _unfold_lines(value)
    events = []
    current_event: dict[str, str] | None = None

    for line in lines:
        if line == "BEGIN:VEVENT":
            current_event = {}
            continue

        if line == "END:VEVENT":
            if current_event is not None:
                events.append(current_event)
            current_event = None
            continue

        if current_event is None or ":" not in line:
            continue

        raw_name, raw_value = line.split(":", 1)
        parts = raw_name.split(";")
        name = parts[0]
        current_event[name] = decode_text(raw_value)
        current_event[f"{name}_RAW"] = line

        for part in parts[1:]:
            if "=" not in part:
                continue

            parameter_name, parameter_value = part.split("=", 1)
            current_event[f"{name}_{parameter_name}"] = parameter_value

        timezone_match = re.search(r"TZID=([^;:]+)", raw_name)
        if timezone_match:
            current_event[f"{name}_TZID"] = timezone_match.group(1)

    return events


def parse_datetime(value: str, timezone_name: str | None = None) -> datetime:
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc,
        )

    if "T" in value:
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
        if timezone_name:
            return parsed.replace(tzinfo=ZoneInfo(timezone_name))

        return parsed.astimezone()

    return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)


def split_values(value: Any) -> list[str]:
    if not value:
        return []

    return [
        item.strip()
        for item in str(value).split(",")
        if item.strip()
    ]


def decode_text(value: str) -> str:
    decoded = (
        value
        .replace(r"\n", "\n")
        .replace(r"\N", "\n")
        .replace(r"\,", ",")
        .replace(r"\;", ";")
        .replace(r"\\", "\\")
    )
    return unescape(decoded).strip()


def _unfold_lines(value: str) -> list[str]:
    unfolded = []

    for line in value.splitlines():
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line.rstrip("\r"))

    return unfolded
