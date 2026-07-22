import base64
import json
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import (
    GOOGLE_CREDENTIALS_B64,
    GOOGLE_CALENDAR_ID,
    GOOGLE_CREDENTIALS_FILE,
    GOOGLE_CREDENTIALS_JSON,
    GOOGLE_TOKEN_B64,
    GOOGLE_TOKEN_FILE,
    GOOGLE_TOKEN_JSON,
)
from models import Event


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
PRIVATE_PROPERTY_NAME = "prutsAgendaOccurrenceId"


class GoogleCalendarSync:
    def __init__(
        self,
        calendar_id: str = GOOGLE_CALENDAR_ID,
        credentials_file: str = GOOGLE_CREDENTIALS_FILE,
        token_file: str = GOOGLE_TOKEN_FILE,
        credentials_json: str | None = GOOGLE_CREDENTIALS_JSON,
        token_json: str | None = GOOGLE_TOKEN_JSON,
        credentials_b64: str | None = GOOGLE_CREDENTIALS_B64,
        token_b64: str | None = GOOGLE_TOKEN_B64,
    ) -> None:
        if not calendar_id or calendar_id == "primary":
            raise ValueError(
                "Refusing to sync without an explicit non-primary "
                "GOOGLE_CALENDAR_ID."
            )

        self.calendar_id = calendar_id
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self.credentials_json = credentials_json or self._decode_b64(credentials_b64)
        self.token_json = token_json or self._decode_b64(token_b64)
        self.service = build(
            "calendar",
            "v3",
            credentials=self._load_credentials(),
        )

    def sync_events(
        self,
        events: list[Event],
        delete_stale: bool = False,
    ) -> tuple[int, int, int]:
        created = 0
        updated = 0
        deleted = 0

        for event in events:
            existing_event_id = self._find_existing_event_id(event)
            body = self._to_calendar_event(event)

            if existing_event_id:
                self.service.events().update(
                    calendarId=self.calendar_id,
                    eventId=existing_event_id,
                    body=body,
                ).execute()
                updated += 1
            else:
                self.service.events().insert(
                    calendarId=self.calendar_id,
                    body=body,
                ).execute()
                created += 1

        if delete_stale:
            deleted = self._delete_stale_events(events)

        return created, updated, deleted

    def _load_credentials(self) -> Credentials:
        credentials = None

        if self.token_json:
            credentials = Credentials.from_authorized_user_info(
                json.loads(self.token_json),
                SCOPES,
            )
        elif self.token_file.exists():
            credentials = Credentials.from_authorized_user_file(
                str(self.token_file),
                SCOPES,
            )

        if credentials and credentials.valid:
            return credentials

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if self.credentials_json:
                flow = InstalledAppFlow.from_client_config(
                    json.loads(self.credentials_json),
                    SCOPES,
                )
            elif self.credentials_file.exists():
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_file),
                    SCOPES,
                )
            else:
                raise FileNotFoundError(
                    f"Missing {self.credentials_file}. Create a Google OAuth "
                    "desktop client and save its downloaded JSON here, or set "
                    "GOOGLE_CREDENTIALS_JSON."
                )

            credentials = flow.run_local_server(port=0)

        self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        return credentials

    @staticmethod
    def _decode_b64(value: str | None) -> str | None:
        if not value:
            return None

        return base64.b64decode(value).decode("utf-8")

    def _find_existing_event_id(self, event: Event) -> str | None:
        try:
            result = self.service.events().list(
                calendarId=self.calendar_id,
                privateExtendedProperty=(
                    f"{PRIVATE_PROPERTY_NAME}={event.occurrence_id}"
                ),
                maxResults=1,
                singleEvents=False,
            ).execute()
        except HttpError as error:
            raise RuntimeError(
                f"Could not search Google Calendar for {event.title!r}: {error}"
            ) from error

        items = result.get("items", [])
        if not items:
            return None

        return items[0]["id"]

    def _delete_stale_events(self, current_events: list[Event]) -> int:
        current_occurrence_ids = {
            event.occurrence_id
            for event in current_events
        }
        deleted = 0
        page_token = None

        while True:
            result = self.service.events().list(
                calendarId=self.calendar_id,
                maxResults=2500,
                pageToken=page_token,
                showDeleted=False,
                singleEvents=False,
                timeMin=datetime.now().astimezone().isoformat(),
            ).execute()

            for calendar_event in result.get("items", []):
                private_properties = (
                    calendar_event
                    .get("extendedProperties", {})
                    .get("private", {})
                )
                occurrence_id = private_properties.get(PRIVATE_PROPERTY_NAME)

                if not occurrence_id:
                    continue

                if occurrence_id in current_occurrence_ids:
                    continue

                self.service.events().delete(
                    calendarId=self.calendar_id,
                    eventId=calendar_event["id"],
                ).execute()
                deleted += 1

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return deleted

    def _to_calendar_event(self, event: Event) -> dict:
        description_parts = []

        if event.description:
            description_parts.append(event.description)

        if event.url:
            description_parts.append(f"Radar: {event.url}")

        if event.categories:
            description_parts.append(f"Categories: {', '.join(event.categories)}")

        if event.topics:
            description_parts.append(f"Topics: {', '.join(event.topics)}")

        body = {
            "summary": event.title,
            "location": event.location,
            "description": "\n\n".join(description_parts),
            "start": {
                "dateTime": event.start.isoformat(),
            },
            "end": {
                "dateTime": event.end_or_default.isoformat(),
            },
            "extendedProperties": {
                "private": {
                    PRIVATE_PROPERTY_NAME: event.occurrence_id,
                    "radarId": event.radar_id,
                    "radarUuid": event.uuid,
                    "source": event.source,
                },
            },
        }

        if event.url:
            body["source"] = {
                "title": "Radar",
                "url": event.url,
            }

        return body
