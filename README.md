# Pruts Agenda

A small project to collect hacker, maker and critical technology events in
Amsterdam and sync them to Google Calendar.

Current sources:

- Radar events in Amsterdam
- Waag's English iCalendar feed
- Hackers & Designers activities
- The Hmm iCalendar feed

Made with ChatGPT and Codex.

## Setup

Install dependencies:

```sh
python3 -m pip install -r requirements.txt
```

Create a Google OAuth desktop client for the Calendar API, download its JSON
file, and save it in this directory as `credentials.json`.

The first sync opens a browser so you can approve access. After that, the
refresh token is stored in `token.json`.

Both files are ignored by git.

For GitHub Actions, store base64-encoded versions of the OAuth JSON files as
encrypted repository secrets instead of committing them:

- `GOOGLE_CREDENTIALS_B64`: base64-encoded contents of `credentials.json`
- `GOOGLE_TOKEN_B64`: base64-encoded contents of `token.json`

On macOS, you can copy the encoded values with:

```sh
base64 -i credentials.json | pbcopy
base64 -i token.json | pbcopy
```

Add them in GitHub under:

```text
Settings -> Secrets and variables -> Actions -> Repository secrets
```

The included workflow in `.github/workflows/sync-calendar.yml` runs daily and
can also be started manually. It syncs the configured calendar and deletes
future Pruts Agenda events that no longer match the current sources/filters.

## Usage

Preview matching events:

```sh
python3 main.py
```

Sync matching events to the configured Pruts Agenda calendar:

```sh
python3 main.py --sync
```

Sync without printing the report:

```sh
python3 main.py --sync --no-report
```

Sync and remove future events that were previously synced by Pruts Agenda but
no longer match the current filters:

```sh
python3 main.py --sync --no-report --delete-stale
```

By default, sync targets this dedicated calendar:

```text
5700514223feffc197c9ac100226a547a3b02716f4a52acdeeacf07313423f88@group.calendar.google.com
```

To sync to a different non-primary calendar, set `GOOGLE_CALENDAR_ID` to that
calendar's ID:

```sh
GOOGLE_CALENDAR_ID="your-calendar-id@group.calendar.google.com" python3 main.py --sync
```

Synced events store a private source occurrence ID in Google Calendar, so
reruns update existing events instead of creating duplicates.
