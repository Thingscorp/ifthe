# The morning briefing

One page, rendered from the same read-only exports the rest of ifthe
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
no external assets. If a section has nothing true to say, it prints one
short line and takes less room.

The renderer never fetches, writes back, or moves anything. It reads
files and writes one HTML file.

## Profiles

`--profile panel` is the default: 800x480 landscape, the reTerminal
class. `--profile card` is 648x480 landscape, pure black on white, for
the 5.83 inch mono panel class (Good Display GDEY0583T81 and kin).
`--profile kindle` is portrait, below.

## Widgets

Every section of the briefing is a widget, and anyone can add one with
a folder of data. No code, no HTML, no CSS: the renderer owns all
markup and escapes every string. The full contract is in
[WIDGETS.md](WIDGETS.md).

At render time the renderer scans two roots: `briefing/widgets/` for
shared widgets, and a `widgets/` folder inside or beside the data
directory for the household's own. A widget folder holds `widget.json`
(id, title, version, slot, order, profiles, template, reads) and an
optional `data.json` in its template's shape. Templates are `lines`
(at most 4), `items` (at most 6), `status` (at most 3), and `text`
(at most 220 characters), plus a one line `glance` slot capped at 48
characters. A widget reads only its own folder and the exports named
in its `reads` list.

The four built in sections (`today`, `home`, `money`, `list`) are
widgets on the same path. A local widget with a reserved id replaces
the built in one. An optional `layout.json` in the data directory can
reorder widgets and hide them. A folder holding a code file is skipped
whole, and a bad widget is skipped with one warning line on stderr:
the page always renders. Setting values live in `settings.json` in
the data directory, keyed by widget id: the generic keys `max_items`,
`show_title`, and `title` are applied to any widget that declares
them, a value that fails validation falls back to the declared
default with a warning, and any other declared key validates without
a rendering effect yet.

Two worked examples live in [widget-examples/](widget-examples/): an
`items` widget that declares a `max_items` setting, and a `status`
widget. That folder is never scanned; copy a folder into a `widgets/`
root to use it.

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

The `kindle/` folder at the repo root is the working package for this:
a server script that renders the PNG, the device fetch-and-draw loop,
and a KUAL extension skeleton.

Without a jailbreak, the Kindle's experimental browser can open the
briefing page on the LAN for a manual glance, but it sleeps on its own
schedule and will not hold the page. The jailbreak path is the real one.
