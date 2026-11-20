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

## On a Kindle

The proven pattern for old Kindles is not the browser. The home server
renders the briefing to a PNG at the panel's exact size, and the Kindle
only has to draw a picture:

    python3 render_briefing.py --data /path/to/exports \
        --profile kindle --out briefing-kindle.html

The kindle profile is portrait, pure black on white, big type, sized
1072x1448 (Paperwhite 3 and later; for a 600x800 Kindle, scale the PNG
down, the layout holds). Convert the HTML to PNG with any headless
browser, serve the PNG on the LAN, and on a jailbroken Kindle a small
loop (the community's onlinescreensaver, or a KUAL extension with
FBInk) fetches it every few minutes and draws it full screen with the
screensaver held off. E-ink keeps the last frame for free while the
device sleeps between refreshes, so a charge lasts weeks. Projects to
borrow from: kindle-wall-display, the Home Assistant Lovelace Kindle
Screensaver, kindle-dashboard. Jailbreak steps depend on model and
firmware; kindlemodding.org's wizard is the current map.

Without a jailbreak, the Kindle's experimental browser can open the
briefing page on the LAN for a manual glance, but it sleeps on its own
schedule and will not hold the page. The jailbreak path is the real one.
