#!/usr/bin/env python3
"""Render the ifthe morning briefing: one calm page for an e-ink panel.

Reads plain JSON files from a data directory (all optional except that a
missing file renders a graceful empty state, never an error):

  agenda.json   {"date": "2026-11-20", "events": [{"time": "9:05 AM",
                 "title": "...", "all_day": false}]}   (agenda exporter)
  status.json   {"services_up": 9, "services_total": 10, "down": ["Mealie"],
                 "backup_last": "02:15", "backup_ok": true}
  budget.json   {"month": "November", "lines": [{"label": "Left to spend",
                 "value": "$1,240"}]}
  list.json     {"title": "Shopping", "items": ["Eggs", "Coffee"]}

Writes a single self-contained HTML file: no scripts, no external assets,
sized for an 800x480 color e-ink panel and readable on any browser.

  python3 render_briefing.py --data ./sample-data --out briefing.html
"""
import argparse, html, json, os
from datetime import datetime

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #f7f4ec; color: #1c1a17; font-family: "Avenir Next",
  "Segoe UI", system-ui, sans-serif; width: 800px; height: 480px;
  padding: 28px 34px; display: flex; flex-direction: column; }
header { display: flex; align-items: baseline; gap: 18px;
  border-bottom: 2px solid #1c1a17; padding-bottom: 10px; }
.clock { font-size: 64px; font-weight: 600; letter-spacing: -1px; }
.day { font-size: 26px; }
main { display: grid; grid-template-columns: 1.35fr 1fr; gap: 8px 36px;
  padding-top: 14px; flex: 1; }
h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 2px;
  color: #5c6650; margin-bottom: 7px; }
section { margin-bottom: 12px; }
ul { list-style: none; font-size: 19px; line-height: 1.45; }
ul .t { display: inline-block; min-width: 102px; padding-right: 12px; color: #44403a; }
ul.money .t { min-width: 132px; }
.muted { color: #8a8578; }
.big { font-size: 21px; line-height: 1.4; }
.ok { color: #44543c; }
.warn { color: #8a5a13; }
footer { border-top: 1px solid #c9c3b4; padding-top: 8px; font-size: 13px;
  color: #8a8578; display: flex; justify-content: space-between; }
.accent { color: #5c6650; }
"""



KINDLE_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #ffffff; color: #000000; font-family: Georgia, serif;
  width: 1072px; height: 1448px; overflow: hidden; padding: 56px 60px; display: flex;
  flex-direction: column; }
header { border-bottom: 4px solid #000; padding-bottom: 22px; }
.clock { font-size: 150px; font-weight: 700; letter-spacing: -2px;
  font-family: "Avenir Next", "Segoe UI", system-ui, sans-serif; }
.day { font-size: 44px; margin-top: 6px; }
main { padding-top: 30px; flex: 1; }
h2 { font-size: 24px; text-transform: uppercase; letter-spacing: 4px;
  margin-bottom: 14px; font-family: "Avenir Next", "Segoe UI", system-ui, sans-serif; }
section { margin-bottom: 40px; }
ul { list-style: none; font-size: 38px; line-height: 1.5; }
ul .t { display: inline-block; min-width: 190px; padding-right: 22px; }
ul.money .t { min-width: 300px; }
.muted { color: #555; }
.big { font-size: 40px; line-height: 1.45; }
footer { border-top: 2px solid #000; padding-top: 16px; font-size: 24px;
  color: #555; display: flex; justify-content: space-between; }
"""

def load(data_dir, name):
    p = os.path.join(data_dir, name)
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


def esc(s):
    return html.escape(str(s))


def agenda_html(agenda):
    if not agenda or not agenda.get("events"):
        return '<li class="muted">Nothing on the calendar.</li>'
    rows = []
    for e in agenda["events"][:6]:
        t = "All day" if e.get("all_day") or not e.get("time") else e["time"]
        rows.append(f'<li><span class="t">{esc(t)}</span>{esc(e.get("title", ""))}</li>')
    return "\n".join(rows)


def home_html(status):
    if not status:
        return '<p class="big muted">No status report yet.</p>'
    up, total = status.get("services_up"), status.get("services_total")
    down = status.get("down") or []
    if down:
        line1 = f'<p class="big warn">{up} of {total} services up. Down: {esc(", ".join(down))}.</p>'
    else:
        line1 = f'<p class="big ok">All {total} services up.</p>'
    if status.get("backup_last"):
        ok = status.get("backup_ok", True)
        cls = "ok" if ok else "warn"
        word = "ran" if ok else "needs a look"
        line2 = f'<p class="big {cls}">Backup {word} at {esc(status["backup_last"])}.</p>'
    else:
        line2 = '<p class="big muted">No backup report yet.</p>'
    return line1 + line2


def budget_html(budget):
    if not budget or not budget.get("lines"):
        return '<p class="big muted">No budget snapshot yet.</p>'
    rows = [f'<li><span class="t">{esc(l.get("label", ""))}</span>{esc(l.get("value", ""))}</li>'
            for l in budget["lines"][:4]]
    return "\n".join(rows)


def list_html(lst):
    if not lst or not lst.get("items"):
        return ""
    items = "\n".join(f"<li>{esc(i)}</li>" for i in lst["items"][:6])
    return (f'<section><h2>{esc(lst.get("title", "List"))}</h2>'
            f"<ul>{items}</ul></section>")


def render(data_dir, now=None, profile="panel"):
    now = now or datetime.now()
    agenda = load(data_dir, "agenda.json")
    status = load(data_dir, "status.json")
    budget = load(data_dir, "budget.json")
    lst = load(data_dir, "list.json")
    clock = now.strftime("%-I:%M")
    day = now.strftime("%A, %B %-d")
    month = (budget or {}).get("month", "Money")
    if profile == "kindle":
        body = f"""<header><div class="clock">{clock}</div><div class="day">{esc(day)}</div></header>
<main>
<section><h2>Today</h2><ul>{agenda_html(agenda)}</ul></section>
<section><h2>Home</h2>{home_html(status)}</section>
<section><h2>{esc(month)}</h2><ul class="money">{budget_html(budget)}</ul></section>
{list_html(lst)}
</main>"""
        css = KINDLE_CSS
    else:
        body = f"""<header><div class="clock">{clock}</div><div class="day">{esc(day)}</div></header>
<main>
<div>
<section><h2>Today</h2><ul>{agenda_html(agenda)}</ul></section>
{list_html(lst)}
</div>
<div>
<section><h2>Home</h2>{home_html(status)}</section>
<section><h2>{esc(month)}</h2><ul class="money">{budget_html(budget)}</ul></section>
</div>
</main>"""
        css = CSS
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>ifthe briefing</title><style>{css}</style></head>
<body>
{body}
<footer><span>ifthe morning briefing</span>
<span>Updated {now.strftime("%-I:%M %p")}</span></footer>
</body></html>"""
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="sample-data")
    ap.add_argument("--out", default="briefing.html")
    ap.add_argument("--profile", choices=["panel", "kindle"], default="panel")
    args = ap.parse_args()
    page = render(args.data, profile=args.profile)
    with open(args.out, "w") as fh:
        fh.write(page)
    print(f"briefing: wrote {args.out} ({len(page)} bytes)")


if __name__ == "__main__":
    main()
