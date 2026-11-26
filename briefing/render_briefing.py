#!/usr/bin/env python3
"""Render the ifthe morning briefing: one page for an e-ink panel.

Reads plain JSON files from a data directory (all optional except that a
missing file renders a graceful empty state, never an error):

  agenda.json   {"date": "2026-11-20", "events": [{"time": "9:05 AM",
                 "title": "...", "all_day": false}]}   (agenda exporter)
  status.json   {"services_up": 9, "services_total": 10, "down": ["Mealie"],
                 "backup_last": "02:15", "backup_ok": true}
  budget.json   {"month": "November", "lines": [{"label": "Left to spend",
                 "value": "$1,240"}]}
  list.json     {"title": "Shopping", "items": ["Eggs", "Coffee"]}
  settings.json {"<widget id>": {"<setting key>": value}}   (optional;
                 values for the settings each widget declares)

Sections are widgets. The four built in sections and any folder widgets
found by the render time scan render through the same path. The widget
contract lives in briefing/WIDGETS.md: data only, host rendered, bounded.

Writes a single self-contained HTML file: no scripts, no external assets,
sized for an 800x480 color e-ink panel and readable on any browser.

  python3 render_briefing.py --data ./sample-data --out briefing.html
"""
import argparse, html, json, os, re, sys
from datetime import datetime

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #f7f4ec; color: #1c1a17; font-family: "Avenir Next",
  "Segoe UI", system-ui, sans-serif; width: 800px; height: 480px;
  overflow: hidden; font-variant-numeric: tabular-nums;
  padding: 28px 34px; display: flex; flex-direction: column; }
header { display: flex; align-items: baseline; gap: 18px;
  border-bottom: 2px solid #1c1a17; padding-bottom: 10px; }
.clock { font-size: 64px; font-weight: 600; letter-spacing: -1px; }
.day { font-size: 26px; }
main { display: grid; grid-template-columns: 1.35fr 1fr; gap: 8px 36px;
  padding-top: 14px; flex: 1; min-height: 0; overflow: hidden; }
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
  width: 1072px; height: 1448px; overflow: hidden; font-variant-numeric: tabular-nums; padding: 56px 60px; display: flex;
  flex-direction: column; }
header { border-bottom: 4px solid #000; padding-bottom: 22px; }
.clock { font-size: 150px; font-weight: 700; letter-spacing: -2px;
  font-family: "Avenir Next", "Segoe UI", system-ui, sans-serif; }
.day { font-size: 44px; margin-top: 6px; }
main { padding-top: 22px; flex: 1; min-height: 0; overflow: hidden; }
h2 { font-size: 24px; text-transform: uppercase; letter-spacing: 4px;
  margin-bottom: 14px; font-family: "Avenir Next", "Segoe UI", system-ui, sans-serif; }
section { margin-bottom: 28px; }
ul { list-style: none; font-size: 38px; line-height: 1.45; }
ul .t { display: inline-block; min-width: 190px; padding-right: 22px; }
ul.money .t { min-width: 300px; }
.muted { color: #555; }
.big { font-size: 40px; line-height: 1.45; }
footer { border-top: 2px solid #000; padding-top: 16px; font-size: 24px;
  color: #555; display: flex; justify-content: space-between; }
"""

CARD_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #ffffff; color: #000000; font-family: "Avenir Next",
  "Segoe UI", system-ui, sans-serif; width: 648px; height: 480px;
  overflow: hidden; font-variant-numeric: tabular-nums; padding: 22px 26px; display: flex; flex-direction: column; }
header { display: flex; align-items: baseline; gap: 14px;
  border-bottom: 2px solid #000; padding-bottom: 8px; }
.clock { font-size: 50px; font-weight: 600; letter-spacing: -1px; }
.day { font-size: 21px; }
main { display: grid; grid-template-columns: 1.35fr 1fr; gap: 6px 28px;
  padding-top: 12px; flex: 1; min-height: 0; overflow: hidden; }
h2 { font-size: 11px; text-transform: uppercase; letter-spacing: 2px;
  color: #444; margin-bottom: 6px; }
section { margin-bottom: 10px; }
ul { list-style: none; font-size: 16px; line-height: 1.45; }
ul .t { display: inline-block; min-width: 84px; padding-right: 10px; color: #333; }
ul.money .t { min-width: 108px; }
.muted { color: #777; }
.big { font-size: 17px; line-height: 1.4; }
footer { border-top: 1px solid #bbb; padding-top: 7px; font-size: 11px;
  color: #777; display: flex; justify-content: space-between; }
"""

# Profiles are data, defined once here. The manifest validator, the
# renderer, and the CLI all read this registry, so a new profile is one
# entry: name, page size in pixels, colour mode ("color" or "mono"),
# the CSS that draws the page, and the layout shape ("columns" is a
# main column plus a side column, "single" is one column top to bottom).
PROFILE_REGISTRY = {
    "panel": {"width": 800, "height": 480, "colour": "color",
              "css": CSS, "layout": "columns"},
    "card": {"width": 648, "height": 480, "colour": "mono",
             "css": CARD_CSS, "layout": "columns"},
    "kindle": {"width": 1072, "height": 1448, "colour": "mono",
               "css": KINDLE_CSS, "layout": "single"},
}
PROFILES = tuple(PROFILE_REGISTRY)
SLOTS = ("main", "side", "glance")
TEMPLATES = ("lines", "items", "status", "text")
RESERVED_IDS = ("today", "home", "money", "list")
MAX_WIDGET_FILE_BYTES = 64 * 1024
MAX_LINES = 4
MAX_ITEMS = 6
MAX_STATUS_LINES = 3
MAX_TEXT_CHARS = 220
MAX_GLANCE_CHARS = 48
MAX_TITLE_CHARS = 48
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXPORT_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
SETTING_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
CODE_SUFFIXES = {
    ".py", ".pyc", ".pyo", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".sh", ".bash", ".zsh", ".pl", ".rb", ".php", ".exe", ".com", ".bat",
    ".cmd", ".ps1", ".jar", ".class",
}


def load(data_dir, name):
    p = os.path.join(data_dir, name)
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


def esc(s):
    return html.escape(str(s))


def warn(message):
    print(f"warning: {message}", file=sys.stderr)


def text_value(value):
    """Return a display string for a scalar, or None for anything else."""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def safe_load_json(path, label):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        warn(f"skipping unreadable {label}: {exc}")
        return None


def make_export_loader(data_dir):
    cache = {}

    def get_export(name):
        if name not in cache:
            path = os.path.join(data_dir, f"{name}.json")
            cache[name] = safe_load_json(path, f"export {name}")
        return cache[name]

    return get_export


def agenda_html(agenda):
    if not agenda or not isinstance(agenda.get("events"), list):
        return '<li class="muted">Nothing on the calendar.</li>'
    events = [e for e in agenda["events"] if isinstance(e, dict)][:6]
    if not events:
        return '<li class="muted">Nothing on the calendar.</li>'
    rows = []
    for e in events:
        t = "All day" if e.get("all_day") or not e.get("time") else e["time"]
        rows.append(f'<li><span class="t">{esc(t)}</span>{esc(e.get("title", ""))}</li>')
    return "\n".join(rows)


def status_lines(status):
    """Shape a status export into status template lines."""
    if not isinstance(status, dict):
        return []
    up = text_value(status.get("services_up"))
    total = text_value(status.get("services_total"))
    down_raw = status.get("down") or []
    down = []
    if isinstance(down_raw, list):
        down = [v for v in (text_value(item) for item in down_raw) if v is not None]
    if down:
        if up is not None and total is not None:
            lines = [{"text": f"{up} of {total} services up. Down: {', '.join(down)}.",
                      "state": "warn"}]
        else:
            lines = [{"text": f"Services down: {', '.join(down)}.",
                      "state": "warn"}]
    elif total is not None:
        lines = [{"text": f"All {total} services up.", "state": "ok"}]
    else:
        lines = []
    if status.get("backup_last"):
        ok = status.get("backup_ok", True)
        word = "ran" if ok else "needs a look"
        lines.append({"text": f"Backup {word} at {status['backup_last']}.",
                      "state": "ok" if ok else "warn"})
    else:
        lines.append({"text": "No backup report yet.", "state": "muted"})
    return lines


def home_html(status):
    if not status:
        return '<p class="big muted">No status report yet.</p>'
    return "".join(
        f'<p class="big {line["state"]}">{esc(line["text"])}</p>'
        for line in status_lines(status)
    )


def budget_html(budget):
    if not budget or not budget.get("lines"):
        return '<p class="big muted">No budget snapshot yet.</p>'
    rows = [f'<li><span class="t">{esc(l.get("label", ""))}</span>{esc(l.get("value", ""))}</li>'
            for l in budget["lines"][:4] if isinstance(l, dict)]
    return "\n".join(rows) if rows else '<p class="big muted">No budget snapshot yet.</p>'


def list_html(lst):
    if not lst or not lst.get("items"):
        return ""
    items = "\n".join(f"<li>{esc(i)}</li>" for i in lst["items"][:6])
    return (f'<section><h2>{esc(lst.get("title", "List"))}</h2>'
            f"<ul>{items}</ul></section>")


def valid_lines(data, limit=MAX_LINES):
    lines = data.get("lines") if isinstance(data, dict) else None
    valid = []
    if isinstance(lines, list):
        for entry in lines:
            if not isinstance(entry, dict):
                continue
            label = text_value(entry.get("label"))
            value = text_value(entry.get("value"))
            if label is not None and value is not None:
                valid.append({"label": label, "value": value})
    return valid[:limit]


def valid_items(data, limit=MAX_ITEMS):
    items = data.get("items") if isinstance(data, dict) else None
    valid = []
    if isinstance(items, list):
        for item in items:
            value = text_value(item)
            if value is not None:
                valid.append(value)
    return valid[:limit]


def valid_status_lines(data, limit=MAX_STATUS_LINES):
    lines = data.get("lines") if isinstance(data, dict) else None
    valid = []
    if isinstance(lines, list):
        for entry in lines:
            if not isinstance(entry, dict):
                continue
            text = text_value(entry.get("text"))
            if text is None:
                continue
            state = entry.get("state")
            valid.append({"text": text,
                          "state": state if state in ("ok", "warn", "muted") else "muted"})
    return valid[:limit]


def builtin_widgets(get_export):
    agenda = get_export("agenda")
    status = get_export("status")
    budget = get_export("budget")
    lst = get_export("list")
    agenda = agenda if isinstance(agenda, dict) else None
    budget = budget if isinstance(budget, dict) else None
    lst = lst if isinstance(lst, dict) else None
    month = text_value(budget.get("month")) if budget else None
    widgets = [
        {
            "manifest": {"id": "today", "title": "Today", "version": "1.0.0",
                         "slot": "main", "order": 10, "profiles": list(PROFILES),
                         "template": "agenda", "reads": ["agenda"]},
            "data": agenda,
            "empty_text": "Nothing on the calendar.",
        },
        {
            "manifest": {"id": "home", "title": "Home", "version": "1.0.0",
                         "slot": "side", "order": 20, "profiles": list(PROFILES),
                         "template": "status", "reads": ["status"]},
            "data": {"lines": status_lines(status)},
            "empty_text": "No status report yet.",
        },
        {
            "manifest": {"id": "money", "title": month or "Money", "version": "1.0.0",
                         "slot": "side", "order": 30, "profiles": list(PROFILES),
                         "template": "lines", "reads": ["budget"]},
            "data": {"lines": budget.get("lines") if budget else []},
            "empty_text": "No budget snapshot yet.",
        },
        {
            "manifest": {"id": "list", "title": "List", "version": "1.0.0",
                         "slot": "main", "order": 40, "profiles": list(PROFILES),
                         "template": "items", "reads": ["list"]},
            "data": lst or {},
            "empty_text": "No list yet.",
            "title_from_data": True,
        },
    ]
    return {w["manifest"]["id"]: w for w in widgets}


def validate_settings(settings):
    if settings is None:
        return None
    if not isinstance(settings, list):
        return "settings must be a list"
    for entry in settings:
        if not isinstance(entry, dict):
            return "each setting must be an object"
        key = entry.get("key")
        if not isinstance(key, str) or not SETTING_KEY_RE.match(key):
            return "a setting has a bad key"
        if entry.get("type") not in ("toggle", "select", "input"):
            return f"setting {key} has an unknown type"
        label = entry.get("label")
        if not isinstance(label, str) or not label:
            return f"setting {key} has no label"
        default = entry.get("default")
        if entry["type"] == "toggle" and default is not None \
                and not isinstance(default, bool):
            return f"setting {key} toggle default must be true or false"
        if entry["type"] == "select":
            options = entry.get("options")
            if not isinstance(options, list) or not options \
                    or not all(isinstance(o, str) for o in options):
                return f"setting {key} select needs a list of options"
            if default is not None and default not in options:
                return f"setting {key} select default is not one of its options"
        if entry["type"] == "input" and default is not None \
                and text_value(default) is None:
            return f"setting {key} input default must be text"
    return None


def validate_manifest(manifest, folder_name):
    if not isinstance(manifest, dict):
        return "widget.json must hold an object"
    for field in ("id", "title", "version", "slot", "order",
                  "profiles", "template", "reads"):
        if field not in manifest:
            return f"missing required field {field}"
    wid = manifest["id"]
    if not isinstance(wid, str) or not ID_RE.match(wid):
        return "id is not a lowercase slug"
    if wid != folder_name:
        return f"id {wid} does not match folder {folder_name}"
    title = manifest["title"]
    if not isinstance(title, str) or not title:
        return "title must be text"
    version = manifest["version"]
    if not isinstance(version, str) or not VERSION_RE.match(version):
        return "version must be major.minor.patch"
    if "author" in manifest and not isinstance(manifest["author"], str):
        return "author must be text"
    if manifest["slot"] not in SLOTS:
        return f"unknown slot {manifest['slot']}"
    order = manifest["order"]
    if not isinstance(order, int) or isinstance(order, bool):
        return "order must be an integer"
    profiles = manifest["profiles"]
    if not isinstance(profiles, list) or not profiles \
            or any(p not in PROFILES for p in profiles) \
            or len(set(profiles)) != len(profiles):
        return "profiles must be a subset of " + ", ".join(PROFILES)
    if manifest["template"] not in TEMPLATES:
        return f"unknown template {manifest['template']}"
    reads = manifest["reads"]
    if not isinstance(reads, list) \
            or any(not isinstance(r, str) or not EXPORT_RE.match(r) for r in reads):
        return "reads must be a list of plain export names"
    return validate_settings(manifest.get("settings"))


def folder_code_file(widget_dir):
    for root, dirs, files in os.walk(widget_dir):
        dirs.sort()
        for filename in sorted(files):
            path = os.path.join(root, filename)
            if os.path.splitext(filename)[1].lower() in CODE_SUFFIXES:
                return filename
            try:
                if os.stat(path).st_mode & 0o111:
                    return filename
                with open(path, "rb") as fh:
                    if fh.read(2) == b"#!":
                        return filename
            except OSError:
                return filename
    return None


def read_widget_file(path, widget_id, kind):
    """Read one widget JSON file. Return (value, error)."""
    try:
        if os.path.getsize(path) > MAX_WIDGET_FILE_BYTES:
            return None, f"{kind} is over 64 KB"
        with open(path) as fh:
            return json.load(fh), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"bad {kind}: {exc}"


def transform_export(export, template, name):
    if not isinstance(export, dict):
        return {}
    if template == "status" and name == "status":
        return {"lines": status_lines(export)}
    if template == "lines" and name == "budget" and "lines" in export:
        return {"lines": export["lines"]}
    if template == "items" and name == "list":
        return {k: export[k] for k in ("title", "items") if k in export}
    shaped = {}
    for key in ("lines", "items", "text", "glance", "title"):
        if key in export:
            shaped[key] = export[key]
    return shaped


def resolve_widget_data(manifest, own_data, get_export):
    resolved = {}
    for name in manifest["reads"]:
        resolved.update(transform_export(get_export(name),
                                         manifest["template"], name))
    if isinstance(own_data, dict):
        resolved.update(own_data)
    return resolved


def load_folder_widget(widget_dir, source, get_export):
    folder_name = os.path.basename(os.path.normpath(widget_dir))
    code = folder_code_file(widget_dir)
    if code is not None:
        warn(f"widget {folder_name}: skipped, folder holds code file {code}")
        return None
    manifest_path = os.path.join(widget_dir, "widget.json")
    if not os.path.exists(manifest_path):
        warn(f"widget {folder_name}: skipped, no widget.json")
        return None
    manifest, error = read_widget_file(manifest_path, folder_name, "widget.json")
    if error is not None:
        warn(f"widget {folder_name}: skipped, {error}")
        return None
    error = validate_manifest(manifest, folder_name)
    if error is not None:
        warn(f"widget {folder_name}: skipped, {error}")
        return None
    own_data = {}
    data_path = os.path.join(widget_dir, "data.json")
    if os.path.exists(data_path):
        data, error = read_widget_file(data_path, manifest["id"], "data.json")
        if error is not None:
            warn(f"widget {manifest['id']}: skipped, {error}")
            return None
        own_data = data if isinstance(data, dict) else {}
    return {
        "manifest": manifest,
        "data": resolve_widget_data(manifest, own_data, get_export),
        "empty_text": "No data yet.",
        "source": source,
    }


def discover_folder_widgets(data_dir, get_export):
    records = {}
    shared_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "widgets")
    roots = [("shared", shared_root)]
    seen = {os.path.realpath(shared_root)}
    data_abs = os.path.abspath(data_dir)
    for candidate in (os.path.join(data_abs, "widgets"),
                      os.path.join(os.path.dirname(data_abs), "widgets")):
        real = os.path.realpath(candidate)
        if real not in seen:
            seen.add(real)
            roots.append(("local", candidate))
    for source, root in roots:
        if not os.path.isdir(root):
            continue
        for entry in sorted(os.listdir(root)):
            widget_dir = os.path.join(root, entry)
            if not os.path.isdir(widget_dir):
                continue
            record = load_folder_widget(widget_dir, source, get_export)
            if record is None:
                continue
            wid = record["manifest"]["id"]
            if source == "shared" and wid in RESERVED_IDS:
                warn(f"widget {wid}: skipped, shared widgets cannot use a reserved id")
                continue
            records[wid] = record
    return records


def load_layout(data_dir):
    layout = {"order": [], "hidden": []}
    path = os.path.join(data_dir, "layout.json")
    if not os.path.exists(path):
        return layout
    data = safe_load_json(path, "layout.json")
    if not isinstance(data, dict):
        if data is not None:
            warn("layout: skipped, layout.json must hold an object")
        return layout
    for key in ("order", "hidden"):
        value = data.get(key, [])
        if isinstance(value, list):
            layout[key] = [v for v in value
                           if isinstance(v, str) and ID_RE.match(v)]
        elif value is not None:
            warn(f"layout: skipped, {key} must be a list of widget ids")
    return layout


def load_settings(data_dir):
    """Read settings.json from the data directory.

    Shape: an object keyed by widget id, each value an object keyed by
    setting key. A missing file is normal. A malformed one is ignored
    with one warning; rendering always proceeds.
    """
    path = os.path.join(data_dir, "settings.json")
    if not os.path.exists(path):
        return {}
    data = safe_load_json(path, "settings.json")
    if data is None:
        return {}
    if not isinstance(data, dict):
        warn("settings: skipped, settings.json must hold an object keyed by widget id")
        return {}
    return data


def setting_value_ok(decl, value):
    kind = decl["type"]
    if kind == "toggle":
        return isinstance(value, bool)
    if kind == "select":
        return value in (decl.get("options") or [])
    return isinstance(value, str)


def resolve_widget_settings(widget, supplied_all):
    """Resolve one widget's effective setting values.

    For each declared setting, a supplied value wins when it validates
    against the declaration; a rejected value warns and falls back to
    the declared default. Supplied keys the widget never declared are
    ignored, and widgets with no declarations (the built ins) resolve
    to nothing, so their settings.json entries have no effect.
    """
    manifest = widget["manifest"]
    declarations = manifest.get("settings") or []
    supplied = supplied_all.get(manifest["id"])
    if not isinstance(supplied, dict):
        supplied = {}
    effective = {}
    for decl in declarations:
        key = decl["key"]
        if key in supplied:
            value = supplied[key]
            if setting_value_ok(decl, value):
                effective[key] = value
            else:
                warn(f"widget {manifest['id']}: setting {key} rejected, using default")
                if "default" in decl:
                    effective[key] = decl["default"]
        elif "default" in decl:
            effective[key] = decl["default"]
    widget["settings"] = effective


def parse_count(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def widget_limit(widget, hard_limit):
    """The max_items setting, parsed and clamped to the hard budget."""
    count = parse_count(widget.get("settings", {}).get("max_items"))
    if count is None:
        return hard_limit
    return max(0, min(count, hard_limit))


def sort_widgets(widgets, layout):
    order_index = {wid: i for i, wid in enumerate(layout["order"])}

    def key(widget):
        wid = widget["manifest"]["id"]
        if wid in order_index:
            return (0, order_index[wid], wid)
        return (1, widget["manifest"]["order"], wid)

    return sorted(widgets, key=key)


def widget_title(widget):
    override = widget.get("settings", {}).get("title")
    if isinstance(override, str) and override:
        return override[:MAX_TITLE_CHARS]
    manifest = widget["manifest"]
    if widget.get("title_from_data"):
        title = text_value(widget["data"].get("title"))
        if title:
            return title
    return manifest["title"]


def section_wrap(widget, inner):
    if widget.get("settings", {}).get("show_title") is False:
        return f"<section>{inner}</section>"
    return f'<section><h2>{esc(widget_title(widget))}</h2>{inner}</section>'


def render_lines_widget(widget):
    lines = valid_lines(widget["data"], widget_limit(widget, MAX_LINES))
    if lines:
        rows = "\n".join(
            f'<li><span class="t">{esc(line["label"])}</span>{esc(line["value"])}</li>'
            for line in lines)
    else:
        rows = f'<p class="big muted">{esc(widget["empty_text"])}</p>'
    return section_wrap(widget, f'<ul class="money">{rows}</ul>')


def render_items_widget(widget):
    items = valid_items(widget["data"], widget_limit(widget, MAX_ITEMS))
    if not items:
        return ""
    items_html = "\n".join(f"<li>{esc(item)}</li>" for item in items)
    return section_wrap(widget, f"<ul>{items_html}</ul>")


def render_status_widget(widget):
    lines = valid_status_lines(widget["data"], widget_limit(widget, MAX_STATUS_LINES))
    if lines:
        inner = "".join(
            f'<p class="big {line["state"]}">{esc(line["text"])}</p>'
            for line in lines)
    else:
        inner = f'<p class="big muted">{esc(widget["empty_text"])}</p>'
    return section_wrap(widget, inner)


def render_text_widget(widget):
    text = text_value(widget["data"].get("text"))
    if text:
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS - 1] + "…"
        inner = f'<p class="big">{esc(text)}</p>'
    else:
        inner = f'<p class="big muted">{esc(widget["empty_text"])}</p>'
    return section_wrap(widget, inner)


def render_agenda_widget(widget):
    data = widget["data"] if isinstance(widget["data"], dict) else None
    return section_wrap(widget, f"<ul>{agenda_html(data)}</ul>")


def glance_line(widget):
    data = widget["data"] if isinstance(widget["data"], dict) else {}
    candidate = text_value(data.get("glance"))
    if candidate is None:
        template = widget["manifest"]["template"]
        if template == "lines":
            lines = valid_lines(data, widget_limit(widget, MAX_LINES))
            candidate = f'{lines[0]["label"]}: {lines[0]["value"]}' if lines else None
        elif template == "items":
            items = valid_items(data, widget_limit(widget, MAX_ITEMS))
            candidate = items[0] if items else None
        elif template == "status":
            lines = valid_status_lines(data, widget_limit(widget, MAX_STATUS_LINES))
            candidate = lines[0]["text"] if lines else None
        elif template == "text":
            candidate = text_value(data.get("text"))
    if candidate is None:
        return None
    if len(candidate) > MAX_GLANCE_CHARS:
        candidate = candidate[:MAX_GLANCE_CHARS - 1] + "…"
    return candidate


def render_glance_widget(widget):
    line = glance_line(widget)
    if line is None:
        return ""
    return section_wrap(widget, f'<p class="big">{esc(line)}</p>')


def render_widget(widget):
    if widget["manifest"]["slot"] == "glance":
        return render_glance_widget(widget)
    template = widget["manifest"]["template"]
    if template == "agenda":
        return render_agenda_widget(widget)
    if template == "lines":
        return render_lines_widget(widget)
    if template == "items":
        return render_items_widget(widget)
    if template == "status":
        return render_status_widget(widget)
    return render_text_widget(widget)


def render(data_dir, now=None, profile="panel"):
    now = now or datetime.now()
    get_export = make_export_loader(data_dir)
    widgets_by_id = builtin_widgets(get_export)
    widgets_by_id.update(discover_folder_widgets(data_dir, get_export))
    supplied_settings = load_settings(data_dir)
    for widget in widgets_by_id.values():
        resolve_widget_settings(widget, supplied_settings)
    layout = load_layout(data_dir)
    hidden = set(layout["hidden"])
    widgets = [w for wid, w in widgets_by_id.items() if wid not in hidden]
    widgets = [w for w in widgets if profile in w["manifest"]["profiles"]]
    widgets = sort_widgets(widgets, layout)
    clock = now.strftime("%-I:%M")
    day = now.strftime("%A, %B %-d")
    profile_spec = PROFILE_REGISTRY[profile]
    if profile_spec["layout"] == "single":
        sections_html = "\n".join(render_widget(w) for w in widgets)
        body = f"""<header><div class="clock">{clock}</div><div class="day">{esc(day)}</div></header>
<main>
{sections_html}
</main>"""
    else:
        main_html = "\n".join(render_widget(w) for w in widgets
                              if w["manifest"]["slot"] in ("main", "glance"))
        side_html = "\n".join(render_widget(w) for w in widgets
                              if w["manifest"]["slot"] == "side")
        body = f"""<header><div class="clock">{clock}</div><div class="day">{esc(day)}</div></header>
<main>
<div>
{main_html}
</div>
<div>
{side_html}
</div>
</main>"""
    css = profile_spec["css"]
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
    ap.add_argument("--profile", choices=list(PROFILE_REGISTRY), default="panel")
    args = ap.parse_args()
    page = render(args.data, profile=args.profile)
    with open(args.out, "w") as fh:
        fh.write(page)
    print(f"briefing: wrote {args.out} ({len(page)} bytes)")


if __name__ == "__main__":
    main()
