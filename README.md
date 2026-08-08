# Pruts Agenda

A small project to collect hacker, maker and critical technology events in
Amsterdam and export them as an iCalendar feed.

Current sources:

- Radar events in Amsterdam
- Waag's English feed
- Hackers & Designers activities
- The Hmm feed
- Critical Infrastructure Lab
- Pakhuis de Zwijger events tagged with Technology
- Manually added events

Built with ChatGPT and Codex. Inspired by http://offbeat.amsterdam/

## Setup

Install dependencies:

```sh
python3 -m pip install -r requirements.txt
```

The included workflow in `.github/workflows/export-ical.yml` runs daily and
can also be started manually. It writes the latest feed to
`public/pruts-agenda.ics` and `public/feed.xml`, and commits them back to the
repo when they change. It also deploys the `public/` directory to GitHub Pages.

## Usage

Preview matching events:

```sh
python3 main.py
```

Write an iCalendar feed file:

```sh
python3 main.py export-ics
```

Manual events live in `manual_events.yml` and are merged into the generated
feed. For all-day multi-day events, the `end` date is exclusive: use the day
after the final day.

Events listed in `deleted_events.yml` are excluded from the generated feed.
Waag multi-day events are also excluded by default.

If any automated source cannot be fetched, `export-ics` keeps the existing
generated feeds unchanged and records the failed source in the digest. This
avoids false deletions or re-added events when a source is temporarily down.

Print the report explicitly:

```sh
python3 main.py report
```

The iCalendar export writes to `public/pruts-agenda.ics`. The RSS export writes
to `public/feed.xml`. Both files can be served from GitHub Pages.

The public website is generated as `public/index.html` from
`templates/index.html`. It contains the event list as static HTML, while
`public/site.js` progressively enhances it with date filtering and clickable
cards.

Preview it locally:

```sh
python3 -m http.server 8000 --directory public
```

Then open `http://localhost:8000/`.

Every export run appends to `SYNC_DIGEST.md`, including runs with no event
changes.
