#!/usr/bin/env python3
"""Read-only Nextcloud CalDAV -> today's agenda.json for the ifthe sleep screen.

Lets the CalDAV server expand recurrences (date_search), then shapes events into a tiny
JSON the front door reads. STRICTLY READ-ONLY: never writes to the calendar; touches no money.
If CalDAV creds are unset it writes an empty agenda and exits 0 (graceful no-op).

Deps (container only): caldav. Imported lazily so the pure shaping logic is testable without it.
"""
import os, sys, json, re
from datetime import datetime, date

OUT = os.environ.get("AGENDA_OUT", "/out/agenda.json")


def _unfold(ics: str) -> str:
    # RFC5545 line folding: continuation lines begin with space or tab.
    return re.sub(r"\r?\n[ \t]", "", ics)


def _fmt_time(dtstart_val: str):
    # Returns (time_str_or_None, all_day_bool). DATE-only value => all-day.
    m = re.search(r"T(\d{2})(\d{2})", dtstart_val)
    if not m:
        return None, True
    h, mn = int(m.group(1)), int(m.group(2))
    ap = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{mn:02d} {ap}", False


def shape_events(ics_list, today: date):
    """Pure: list of per-event ICS strings -> sorted [{time, title, all_day}] for `today`."""
    out = []
    for ics in ics_list:
        for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", _unfold(ics or ""), re.S):
            fields = {}
            for line in block.strip().splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    fields[key.split(";", 1)[0].upper()] = (key, val.strip())
            if "DTSTART" not in fields:
                continue
            raw_key, dtstart = fields["DTSTART"]
            day = re.match(r"(\d{4})(\d{2})(\d{2})", dtstart)
            if not day:
                continue
            ev_date = date(int(day.group(1)), int(day.group(2)), int(day.group(3)))
            if ev_date != today:
                continue
            time_str, all_day = _fmt_time(dtstart)
            if "VALUE=DATE" in raw_key.upper():
                all_day = True
            title = fields.get("SUMMARY", ("", "(untitled)"))[1] or "(untitled)"
            out.append({"time": time_str, "title": title, "all_day": all_day,
                        "_sort": dtstart})
    out.sort(key=lambda e: (not e["all_day"], e["_sort"]))
    for e in out:
        e.pop("_sort", None)
    return out


def write(events, today: date):
    payload = {"date": today.isoformat(), "events": events}
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"agenda: wrote {len(events)} event(s) -> {OUT}")


def main():
    url = os.environ.get("CALDAV_URL", "")
    user = os.environ.get("CALDAV_USER", "")
    pw = os.environ.get("CALDAV_APP_PASSWORD", "")
    today = datetime.now().date()
    if not (url and user and pw):
        print("CalDAV not configured: writing empty agenda (no-op).")
        write([], today)
        return
    import caldav  # lazy: only needed when actually fetching
    from datetime import datetime as _dt, time as _time
    client = caldav.DAVClient(url=url, username=user, password=pw)
    start = _dt.combine(today, _time.min)
    end = _dt.combine(today, _time.max)
    ics_list = []
    for cal in client.principal().calendars():
        try:
            for ev in cal.date_search(start=start, end=end, expand=True):
                ics_list.append(ev.data)
        except Exception as e:  # one bad calendar shouldn't kill the run
            print(f"  skip calendar {cal}: {e}")
    write(shape_events(ics_list, today), today)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"agenda export failed: {e}", file=sys.stderr)
        sys.exit(1)
