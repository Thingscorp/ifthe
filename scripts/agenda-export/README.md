# Agenda Exporter

Read-only Nextcloud CalDAV → `$DATA_ROOT/dashboard/agenda.json`, which the front-door
sleep screen reads to show today's agenda. **Never writes to the calendar.**

## Run (containerized, recommended)
Part of `docker-compose.dashboard.yml`. Set in `.env`:

```bash
NEXTCLOUD_CALDAV_URL=https://home.local:8081/remote.php/dav
NEXTCLOUD_CALDAV_USER=russ
NEXTCLOUD_CALDAV_APP_PASSWORD=xxxx-xxxx-xxxx   # Nextcloud → Security → app password
AGENDA_INTERVAL=900   # seconds between refreshes
```

If those are unset the exporter writes an **empty** agenda and exits 0; the sleep screen
then shows "No events today" rather than breaking.

## How it works
- Lets the CalDAV server expand recurrences (`date_search(..., expand=True)`) so weekly
  events show up correctly.
- `shape_events()` (pure, dependency-free) turns the returned VEVENTs into
  `{ "date": "YYYY-MM-DD", "events": [ { "time": "4:00 PM", "title": "...", "all_day": false } ] }`.
- Output is mounted read-only into the front door at `/srv/data/agenda.json`.

## Test
`shape_events` is covered hermetically (no network, no caldav dep) by
`tests/test_agenda_export.py`.
