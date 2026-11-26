#!/usr/bin/env python3
"""Hermetic tests for scripts/agenda-export/agenda_export.py shape_events (no caldav, no network)."""
import sys, importlib.util, json, os, tempfile
from datetime import date
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / "scripts" / "agenda-export" / "agenda_export.py"
spec = importlib.util.spec_from_file_location("agenda_export", MOD)
ae = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ae)  # top-level import must NOT require caldav (lazy)

results = []
def check(name, cond, detail=""): results.append((name, bool(cond), detail))

today = date.today()
ymd = today.strftime("%Y%m%d")
timed   = f"BEGIN:VEVENT\nSUMMARY:Soccer practice\nDTSTART:{ymd}T160000Z\nEND:VEVENT"
allday  = f"BEGIN:VEVENT\nSUMMARY:Trash day\nDTSTART;VALUE=DATE:{ymd}\nEND:VEVENT"
other   = f"BEGIN:VEVENT\nSUMMARY:Old event\nDTSTART:20200101T100000Z\nEND:VEVENT"
folded  = f"BEGIN:VEVENT\nSUMMARY:Long title that is\n  folded across lines\nDTSTART:{ymd}T090000Z\nEND:VEVENT"
cal = "BEGIN:VCALENDAR\n" + "\n".join([timed, allday, other, folded]) + "\nEND:VCALENDAR"

ev = ae.shape_events([cal], today)
check("excludes events not on today", len(ev) == 3, f"got {len(ev)}")
check("all-day sorts before timed", ev and ev[0]["all_day"] is True and ev[0]["title"] == "Trash day")
timed_events = [e for e in ev if not e["all_day"]]
check("timed event time formatted 12h", any(e["time"] == "4:00 PM" and e["title"] == "Soccer practice" for e in timed_events))
check("09:00 -> 9:00 AM", any(e["time"] == "9:00 AM" for e in timed_events))
check("line folding unwrapped in title", any("folded across lines" in e["title"] for e in timed_events))
check("_fmt_time DATE-only is all-day", ae._fmt_time("20260623") == (None, True))
check("_fmt_time timed", ae._fmt_time("20260623T133000Z") == ("1:30 PM", False))
check("empty list -> no events", ae.shape_events([], today) == [])

# main() with blank CalDAV credentials: a graceful no-op. It reads
# CALDAV_URL / CALDAV_USER / CALDAV_APP_PASSWORD from the environment at
# call time and writes to the module-level OUT (from AGENDA_OUT at import),
# so point OUT at a temp file, blank the credentials, and call it directly.
with tempfile.TemporaryDirectory() as td:
    out_path = Path(td) / "agenda.json"
    saved_out = ae.OUT
    cred_keys = ("CALDAV_URL", "CALDAV_USER", "CALDAV_APP_PASSWORD")
    saved_env = {k: os.environ.get(k) for k in cred_keys}
    ae.OUT = str(out_path)
    for k in cred_keys:
        os.environ[k] = ""
    try:
        ret = ae.main()
        payload = json.loads(out_path.read_text()) if out_path.is_file() else None
    finally:
        ae.OUT = saved_out
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    check("main with blank CalDAV creds returns cleanly", ret is None)
    check("main with blank CalDAV creds writes an agenda file", payload is not None)
    check("blank-creds agenda has an empty events list",
          payload is not None and payload.get("events") == [])
    check("blank-creds agenda carries today's date",
          payload is not None and payload.get("date") == today.isoformat())

passed = sum(1 for _, ok, _ in results if ok)
fails = [(n, d) for n, ok, d in results if not ok]
print(f"\nagenda_export: {passed}/{len(results)} checks passed")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}" + (f"   [{d}]" if (not ok and d) else ""))
sys.exit(1 if fails else 0)
