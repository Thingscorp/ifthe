# Briefing widgets

Status: implemented in briefing/render_briefing.py, with tests in
tests/test_briefing_widgets.py. This spec takes the
Pebble model (one manifest per module, declared capabilities, host
rendered glance surfaces, config as data) and fits it to the briefing.

A widget is one small section of the morning briefing, supplied as
data. Anyone can add one by adding a folder. Nobody writes renderer
code, HTML, CSS or scripts to do it.

## Where widgets live

Two roots, scanned in this order at render time:

1. `briefing/widgets/` in this repo: shared widgets, reviewed like any
   other code here.
2. A `widgets/` folder inside or next to the data directory passed
   with `--data`: the household's own widgets. Private widgets live
   here and are never committed, the same rule as `ai/memory/`.

A widget is a folder named for its id:

```
widgets/
  land-hunt/
    widget.json     the manifest, required
    data.json       the widget's own data, optional
    README.md       what it shows and where its data comes from, optional
```

## The manifest: widget.json

```json
{
  "id": "land-hunt",
  "title": "Land hunt",
  "version": "1.0.0",
  "author": "Russ",
  "slot": "main",
  "order": 40,
  "profiles": ["panel", "card", "kindle"],
  "template": "items",
  "reads": ["list"],
  "settings": []
}
```

| Field | Required | Rule |
| --- | --- | --- |
| `id` | yes | Lowercase slug. Must match the folder name. Unique across both roots; the local root wins a tie, so a household can override a shared widget. |
| `title` | yes | The section heading, printed as given. Keep it short. |
| `version` | yes | `major.minor.patch`. An update keeps the id and raises the version. |
| `author` | no | Name or handle. Shown nowhere on the page; kept for the index. |
| `slot` | yes | `main` (left column on panel and card, top to bottom on kindle), `side` (right column), or `glance` (one line only, see below). |
| `order` | yes | Integer. Lower renders first inside the slot. Ties break by id. |
| `profiles` | yes | Subset of `panel`, `card`, `kindle`. The widget renders only on these profiles. |
| `template` | yes | One of `lines`, `items`, `status`, `text`. See templates below. |
| `reads` | yes | Export names the widget may read from the data directory, for example `agenda`, `status`, `budget`, `list`, or a name the household's exporters write. An empty list means the widget reads only its own `data.json`. Nothing outside this list is opened. |
| `settings` | no | Clay style settings declarations, see below. Default empty. |

Unknown fields are ignored. A missing required field, a bad id, or an
unknown template or slot skips the widget (see failure rules).

## Identity

A widget's id is its name in every pack, index, and settings file,
so it is made once and then left alone:

- Tooling generates the id when a widget is published (the
  converter, for example, derives it from the Pebble package name).
  A hand-picked id is fine for a private widget that never leaves
  the house.
- Once a widget is published, its id is never hand edited. An update
  keeps the id and raises the version. Publishing the same widget
  under a new id makes it a different widget, and the old id is
  retired, not reused by another widget.

## Templates

The renderer owns all markup. A widget picks a template and supplies
data in that template's shape. Every string is escaped. No field is
ever treated as HTML.

### lines

Label and value rows, the Money shape.

```json
{ "lines": [ { "label": "Left to spend", "value": "$1,240" } ] }
```

At most 4 lines render. Extra lines are dropped.

### items

A plain list, the Shopping shape.

```json
{ "title": "This week", "items": ["Eggs", "Coffee"] }
```

The manifest `title` wins if both are present. At most 6 items render.

### status

Big lines with a state, the Home shape.

```json
{ "lines": [ { "text": "All 10 services up.", "state": "ok" },
             { "text": "Backup ran at 02:15.", "state": "ok" } ] }
```

`state` is one of `ok`, `warn`, `muted`. At most 3 lines render.

### text

One short paragraph for a note that fits no other shape. At most 220
characters render; longer text is cut with an ellipsis.

## Data

A widget's data comes from at most two places:

1. Its own `data.json`, in its template's shape.
2. The shared exports named in `reads`, read from the data directory
   with the shapes already documented in briefing/README.md.

If a template needs a field the data does not have, the widget renders
its empty state: one short muted line, or nothing for `items`. Data is
display text only. For money that means labeled lines a shaping step
already produced, never the raw ledger, never account numbers, never
single transactions.

A widget may also carry a `glance` string in its data:

```json
{ "items": ["..."], "glance": "Land hunt: 3 new parcels" }
```

On profiles with no room for the full widget (today: none, reserved
for a smaller surface), the renderer may print the glance line alone.
At most 48 characters. This is the AppGlance rule: one line, host
rendered, expires with the data file.

## Timed items

Some briefing data is a list of moments rather than a snapshot: the
day's events are the first example. A timed item is the shared shape
for one moment, modelled on the Pebble timeline pin and cut down to
display only:

```json
{ "id": "dentist-2026-11-21", "time": "2026-11-21T15:30:00",
  "layout": "calendar", "title": "Dentist", "body": "Cleaning, 30 min." }
```

| Field | Rule |
| --- | --- |
| `id` | Stable id for the item, at most 64 characters. An id is never reused, even after the item is deleted: a corrected item keeps its id, and a new moment gets a new id. |
| `time` | When the moment happens, ISO 8601. |
| `layout` | One of a closed list: `generic`, `calendar`, `weather`, `sports`. The renderer picks the shape; the item supplies only text. |
| `title` | A short heading. |
| `body` | Detail text, at most 512 characters. |

Display only, by product rule: a timed item has no actions, sends no
notifications, and carries no reminders. It prints while its data
file is current and expires with the file, like the glance line.
This section fixes the data contract only; renderer support for
timed items is future work.

## Settings (optional)

A widget may declare settings the household can change, Clay style.
The widget ships declarations only; values live in one file,
`settings.json` in the data directory, keyed by widget id.

Declaration, inside `widget.json`:

```json
"settings": [
  { "key": "max_items", "type": "select", "label": "Show at most",
    "options": ["3", "6"], "default": "6" },
  { "key": "show_prices", "type": "toggle", "label": "Show prices",
    "default": true }
]
```

Types: `toggle`, `select`, `input`. A setting may only shape the
widget's own data (counts, labels, which lines). It can never widen
`reads`, change the slot, or turn on a fetch.

At render time the renderer reads `settings.json` from the data
directory. A missing file is normal; a malformed one is ignored with
one warning, and rendering proceeds. For each declared setting, a
supplied value wins when it validates against the declaration: a
select value must be one of its options, a toggle value must be true
or false, an input value must be text. A rejected value warns,
naming the widget and the key, and the declared default applies.
Supplied keys the widget never declared are ignored, and built in
widgets declare no settings, so `settings.json` entries for them
have no effect.

Three generic keys are applied for any widget that declares them:

| Key | Effect |
| --- | --- |
| `max_items` | Caps the widget's rendered lines, items, or status rows at the value, and never above the template's hard budget. |
| `show_title` | When false, the widget renders without its heading. |
| `title` | Replaces the widget's heading text, truncated to 48 characters. |

Any other declared key validates and resolves, but has no rendering
effect yet. Declaring a custom key alone changes nothing; a key
changes output only when the renderer honors it, as it does the
three generic keys above.

## Layout control

The household, not the widget author, has the last word on the page.
An optional `layout.json` in the data directory:

```json
{ "order": ["today", "land-hunt", "home", "money"],
  "hidden": ["list"] }
```

`order` lists widget ids in page order and overrides manifest order
across slots. `hidden` removes widgets from every profile. A widget
not named in `order` keeps its manifest place after the named ones.

## Built in widgets

The four current sections are built in widgets with reserved ids, so
one code path renders everything:

| id | slot | template | reads |
| --- | --- | --- | --- |
| `today` | main | agenda shape (special case, see renderer) | `agenda` |
| `list` | main | items | `list` |
| `home` | side | status | `status` |
| `money` | side | lines | `budget` |

Reserved ids cannot be reused by folder widgets, except that a local
widget with a reserved id replaces the built in one. That is the
supported way to restyle a built in section.

## Packs

A pack is how widgets travel together. A pack is a folder of widget
folders plus one `pack.json` at its root:

```
morning-pack/
  pack.json
  land-hunt/
    widget.json
    data.json
  house-plants/
    widget.json
```

```json
{ "name": "@russ/morning-pack", "version": "1.0.0",
  "widgets": ["land-hunt", "house-plants"] }
```

| Field | Rule |
| --- | --- |
| `name` | Scoped name: an `@` handle, a slash, then a slug. Unique in the index. |
| `version` | `major.minor.patch`, the same rule as a widget version. |
| `widgets` | The ids of the widgets the pack contains. One folder each, named for the id, and each folder a normal widget folder. |

Installing a pack is one command that copies the pack's widget
folders into a widgets root; from there each widget follows the
normal discovery and failure rules, so a bad widget in a pack is
skipped like any other. The install command itself is future work;
this section fixes the format it will read.

## The index

The public index is the catalog of published widgets and packs. It
holds three record kinds, kept separate:

1. **Listing**, one per widget: the widget `id`, its `title`, the
   author's id, a `category`, and two counters the index maintains,
   `installs` and `likes`.
2. **Per-surface assets**, one set per listing: a `description` and a
   preview image for each profile (`panel`, `card`, `kindle`), so a
   household can see a widget as it would print on their own surface
   before installing it.
3. **Release**, one per published version of a pack: the `version`,
   release `notes`, and the pack's `checksum`, so an install can
   check that the pack it fetched is the pack that was published.

The index is a catalog, not a copy. Listing data never goes into the
widget folder: `widget.json` stays the author's manifest, and the
index records point at the widget (or the pack that carries it)
without changing it. A widget works installed from a copied folder
with no index entry at all, and a listing can exist for a widget no
one has installed yet.

## Safety rules

These are the ifthe rules, unchanged, applied to widgets:

1. The renderer never fetches, writes back, or moves anything. It
   reads files and writes one HTML file.
2. Widgets are data only. A widget folder containing code files
   (`.py`, `.js`, `.sh`, or anything executable) is skipped whole.
3. A widget reads only its own folder plus the exports in `reads`.
   Paths are plain file names in the data directory; no subfolders, no
   parent paths, no absolute paths.
4. No scripts, no external assets, no links, no images in widget
   output. The page rules from briefing/README.md still hold.
5. Exporters stay guarded by `scripts/guard-readonly.sh`. Widgets sit
   downstream of the guard and get no path around it. Nothing a widget
   can declare gives it a way to move money or change a service.

## Failure rules

One bad widget never blanks the morning.

1. Bad JSON, a missing required field, an unknown template, slot or
   profile, an oversize data file (over 64 KB), or a code file in the
   folder: skip that widget, print one warning line to stderr naming
   the widget id and the reason, render the rest.
2. Data in the wrong shape for its template: render the empty state.
3. If every widget fails, the page still renders with the clock, the
   date and the footer.

## Adding a widget, start to finish

1. Write `widget.json` from the manifest example above into a new
   folder named for your id: under `briefing/widgets/` to share it, or
   under a local `widgets/` folder to keep it private.
2. Edit `widget.json`: id, title, slot, order, profiles, template,
   reads.
3. Put today's data in `data.json`, or point `reads` at an export your
   exporter already writes.
4. Render and look at it on every profile you declared:

```bash
python3 briefing/render_briefing.py --data /path/to/exports \
    --profile panel --out briefing.html
```

5. To share it, send the folder. To publish it, open a pull request
   adding it under `briefing/widgets/`. There is no store and no
   review queue beyond the repo's own; a folder copied into a local
   `widgets/` root works with no one's permission.
