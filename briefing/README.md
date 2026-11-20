# The morning briefing

One calm page, rendered from the same read-only exports the rest of ifthe
already produces. Built for a color e-ink panel by the door, readable in
any browser.

```bash
python3 briefing/render_briefing.py --data briefing/sample-data --out briefing.html
```

Inputs (all optional; a missing file renders a graceful empty state):

| File | From | Holds |
| --- | --- | --- |
| `agenda.json` | `scripts/agenda-export/` | today's events |
| `status.json` | your health checks | services up/total, what is down, last backup |
| `budget.json` | a shaping step over `ledger.json` | a few labeled money lines for the month |
| `list.json` | yours to write | any tracked list: shopping, packing, the hunt |

Design rules, in order: one screen, no scrolling at 800x480, no scripts,
no external assets, nothing that shouts. If a section has nothing true to
say, it says so quietly and takes less room.

The renderer never fetches, writes back, or moves anything. It reads
files and writes one HTML file.
