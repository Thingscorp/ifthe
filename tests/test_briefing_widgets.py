#!/usr/bin/env python3
"""Hermetic tests for briefing widget discovery and rendering."""
import contextlib, html, importlib.util, io, json, re, shutil, sys, tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "briefing" / "render_briefing.py"
SAMPLE = REPO / "briefing" / "sample-data"
spec = importlib.util.spec_from_file_location("render_briefing", MOD)
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)

NOW = datetime(2026, 11, 21, 7, 5)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def make_case(base):
    data = base / "data"
    data.mkdir()
    for name in ("agenda", "status", "budget", "list"):
        shutil.copyfile(SAMPLE / f"{name}.json", data / f"{name}.json")
    widgets = base / "widgets"
    widgets.mkdir()
    return data, widgets


def write_widget(widgets, folder, title=None, slot="main", order=50,
                 profiles=None, template="items", reads=None, data=None,
                 settings=None, extra=None, raw_manifest=None):
    widget_dir = widgets / folder
    widget_dir.mkdir()
    if raw_manifest is not None:
        (widget_dir / "widget.json").write_text(raw_manifest)
    else:
        manifest = {
            "id": folder,
            "title": title or folder,
            "version": "1.0.0",
            "author": "Test",
            "slot": slot,
            "order": order,
            "profiles": profiles or ["panel", "card", "kindle"],
            "template": template,
            "reads": reads or [],
        }
        if settings is not None:
            manifest["settings"] = settings
        (widget_dir / "widget.json").write_text(json.dumps(manifest))
    if data is not None:
        (widget_dir / "data.json").write_text(json.dumps(data))
    for name, content in (extra or {}).items():
        (widget_dir / name).write_text(content)
    return widget_dir


def render(data, profile="panel"):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        page = rb.render(str(data), now=NOW, profile=profile)
    return page, err.getvalue()


def section(page, title):
    match = re.search(
        r"<section><h2>" + re.escape(title) + r"</h2>(.*?)</section>",
        page, re.S)
    return match.group(1) if match else ""


# Discovery and ordering, beside the data directory.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "alpha", title="Alpha", order=10,
                 data={"items": ["Alpha item"]})
    write_widget(widgets, "beta", title="Beta", order=30, template="lines",
                 data={"lines": [{"label": "Beta label", "value": "Beta value"}]})
    write_widget(widgets, "gamma", title="Gamma", order=5, slot="side",
                 template="status",
                 data={"lines": [{"text": "Gamma is fine.", "state": "ok"}]})
    page, err = render(data)
    check("discovery finds widgets beside the data directory",
          "Alpha item" in page and "Beta label" in page and "Gamma is fine." in page)
    check("valid widgets render without warnings", err == "", err.strip())
    check("manifest order and id tie break order the main slot",
          page.index("Alpha") < page.index("Today")
          < page.index("Beta") < page.index("Shopping"))
    check("side slot order puts gamma before home",
          page.index("Gamma") < page.index("Home"))

# Reads: a widget with no data.json renders the export it declares.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "from-list", title="From list", reads=["list"])
    page, _ = render(data)
    check("reads pulls the named export into the widget",
          "Eggs" in section(page, "From list"))

# Budgets: lines, items, status, text, and glance are all capped.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "many-lines", title="Many lines", template="lines",
                 data={"lines": [{"label": f"Line {i}", "value": str(i)}
                                  for i in range(1, 7)]})
    write_widget(widgets, "many-items", title="Many items",
                 data={"items": [f"Item {i}" for i in range(1, 9)]})
    write_widget(widgets, "many-status", title="Many status", template="status",
                 slot="side",
                 data={"lines": [{"text": f"State {i}", "state": "ok"}
                                  for i in range(1, 6)]})
    write_widget(widgets, "long-text", title="Long text", template="text",
                 data={"text": "x" * 250})
    write_widget(widgets, "long-glance", title="Long glance", slot="glance",
                 template="items", data={"glance": "g" * 60})
    page, _ = render(data)
    check("lines budget keeps four of six",
          "Line 4" in page and "Line 5" not in page and "Line 6" not in page)
    check("items budget keeps six of eight",
          "Item 6" in page and "Item 7" not in page and "Item 8" not in page)
    check("status budget keeps three of five",
          "State 3" in page and "State 4" not in page and "State 5" not in page)
    text_match = re.search(r"<h2>Long text</h2><p class=\"big\">([^<]+)</p>", page)
    text_out = html.unescape(text_match.group(1)) if text_match else ""
    check("text budget renders 220 characters with an ellipsis",
          len(text_out) == 220 and text_out.endswith("…"),
          f"len={len(text_out)}")
    glance_match = re.search(
        r"<h2>Long glance</h2><p class=\"big\">([^<]+)</p>", page)
    glance_out = html.unescape(glance_match.group(1)) if glance_match else ""
    check("glance budget renders one 48 character line",
          len(glance_out) == 48 and glance_out.endswith("…"),
          f"len={len(glance_out)}")

# Escaping: widget strings are never treated as markup.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "safe", title="Safe <Title>",
                 data={"items": ["<b>Eggs</b>"]})
    page, _ = render(data)
    check("widget strings are escaped",
          "Safe &lt;Title&gt;" in page and "&lt;b&gt;Eggs&lt;/b&gt;" in page
          and "<b>Eggs</b>" not in page)

# A folder holding code is skipped whole.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "code-widget", title="Code widget",
                 data={"items": ["Should not render"]},
                 extra={"run.py": "print('hello')\n"})
    page, err = render(data)
    check("executable folder is skipped whole",
          "Code widget" not in page and "Should not render" not in page)
    check("executable folder skip warns with the widget id and reason",
          "widget code-widget: skipped" in err and "code file" in err,
          err.strip())

# Malformed widgets fail alone; the page and good widgets still render.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "broken", raw_manifest="{not json")
    write_widget(widgets, "oversize", title="Oversize", template="text",
                 data={"text": "x" * 70000})
    write_widget(widgets, "good", title="Good", data={"items": ["Good item"]})
    page, err = render(data)
    check("malformed widget is isolated",
          "Good item" in page and "Today" in page)
    check("bad JSON skip warns with the widget id",
          "widget broken: skipped" in err, err.strip())
    check("oversize data skip warns with the widget id",
          "widget oversize: skipped" in err and "over 64 KB" in err,
          err.strip())

# Settings declarations validate: a sound one renders, a bad one skips.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "tuned", title="Tuned", data={"items": ["Tuned item"]},
                 settings=[{"key": "show_prices", "type": "toggle",
                            "label": "Show prices", "default": True}])
    write_widget(widgets, "bad-settings", title="Bad settings",
                 data={"items": ["Should not render"]},
                 settings=[{"key": "pick", "type": "select",
                            "label": "Pick one"}])
    page, err = render(data)
    check("valid settings declaration renders",
          "Tuned item" in page)
    check("invalid settings declaration skips the widget",
          "Bad settings" not in page
          and "widget bad-settings: skipped" in err, err.strip())

# A local widget with a reserved id replaces the built in section.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "list", title="Pantry", order=40,
                 data={"items": ["Rice", "Beans"]})
    page, _ = render(data)
    check("reserved id replacement renders the local widget",
          "Pantry" in page and "Rice" in page)
    check("reserved id replacement removes the built in section",
          "Shopping" not in page and "Eggs" not in page)

# A shared widget cannot take a reserved id.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    fake_root = Path(td) / "fake-briefing"
    shared_widget = fake_root / "widgets" / "home"
    shared_widget.mkdir(parents=True)
    (shared_widget / "widget.json").write_text(json.dumps({
        "id": "home", "title": "Fake home", "version": "1.0.0",
        "slot": "side", "order": 1, "profiles": ["panel"],
        "template": "status", "reads": [],
    }))
    old_file = rb.__file__
    rb.__file__ = str(fake_root / "render_briefing.py")
    try:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            records = rb.discover_folder_widgets(
                str(data), rb.make_export_loader(str(data)))
    finally:
        rb.__file__ = old_file
    check("shared widget with a reserved id is skipped",
          "home" not in records
          and "shared widgets cannot use a reserved id" in err.getvalue(),
          err.getvalue().strip())

# layout.json hides widgets and overrides order across slots.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "layout.json").write_text(json.dumps(
        {"order": ["money", "today"], "hidden": ["list"]}))
    page, _ = render(data, profile="kindle")
    check("layout hidden removes the widget from every profile",
          "Shopping" not in page)
    check("layout order overrides manifest order across slots",
          page.index("November") < page.index("Today") < page.index("Home"))
    (data / "layout.json").write_text(json.dumps({"order": ["list", "today"]}))
    page, _ = render(data)
    check("layout order reorders within the panel main slot",
          page.index("Shopping") < page.index("Today"))

# Settings values: applied generically, validated, with default fallback.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "capped", title="Capped",
                 data={"items": [f"Pick {i}" for i in range(1, 7)]},
                 settings=[{"key": "max_items", "type": "select",
                            "label": "Show at most", "options": ["2", "6"],
                            "default": "6"}])
    (data / "settings.json").write_text(json.dumps(
        {"capped": {"max_items": "2"}}))
    page, err = render(data)
    check("max_items setting caps items below the hard budget",
          "Pick 2" in page and "Pick 3" not in page)
    check("a valid supplied setting renders without warnings",
          err == "", err.strip())

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "headless", title="Headless",
                 data={"items": ["No heading item"]},
                 settings=[{"key": "show_title", "type": "toggle",
                            "label": "Show title", "default": True}])
    (data / "settings.json").write_text(json.dumps(
        {"headless": {"show_title": False}}))
    page, _ = render(data)
    check("show_title false renders the widget without its heading",
          "No heading item" in page and "<h2>Headless</h2>" not in page)

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "renamed", title="Original heading",
                 data={"items": ["Renamed item"]},
                 settings=[{"key": "title", "type": "input",
                            "label": "Heading", "default": "Original heading"}])
    (data / "settings.json").write_text(json.dumps(
        {"renamed": {"title": "Custom heading"}}))
    page, _ = render(data)
    check("title setting replaces the widget heading",
          "<h2>Custom heading</h2>" in page
          and "Original heading" not in page)
    (data / "settings.json").write_text(json.dumps(
        {"renamed": {"title": "T" * 60}}))
    page, _ = render(data)
    title_match = re.search(r"<h2>(T+)</h2>", page)
    check("title setting is truncated to 48 characters",
          title_match is not None and len(title_match.group(1)) == 48)

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "fallback", title="Fallback",
                 data={"items": [f"Fall {i}" for i in range(1, 7)]},
                 settings=[{"key": "max_items", "type": "select",
                            "label": "Show at most", "options": ["2", "6"],
                            "default": "2"}])
    (data / "settings.json").write_text(json.dumps(
        {"fallback": {"max_items": "5"}}))
    page, err = render(data)
    check("invalid select value falls back to the declared default",
          "Fall 2" in page and "Fall 3" not in page)
    check("rejected setting warns naming the widget and the key",
          "widget fallback" in err and "max_items" in err
          and "rejected" in err, err.strip())

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "plain", title="Plain",
                 data={"items": ["Plain item"]})
    (data / "settings.json").write_text("{not json")
    page, err = render(data)
    check("malformed settings.json is ignored and the page renders",
          "Plain item" in page and "Today" in page)
    check("malformed settings.json warns once about settings",
          "settings" in err, err.strip())

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "narrow", title="Narrow",
                 data={"items": ["One", "Two", "Three"]},
                 settings=[{"key": "show_title", "type": "toggle",
                            "label": "Show title", "default": True}])
    (data / "settings.json").write_text(json.dumps(
        {"narrow": {"max_items": "1"},
         "today": {"show_title": False}}))
    page, _ = render(data)
    check("a supplied value for an undeclared key is ignored",
          "One" in page and "Two" in page and "Three" in page)
    check("settings entries for a built in widget are ignored",
          "<h2>Today</h2>" in page)

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "greedy", title="Greedy",
                 data={"items": [f"Grab {i}" for i in range(1, 9)]},
                 settings=[{"key": "max_items", "type": "input",
                            "label": "Show at most", "default": "6"}])
    (data / "settings.json").write_text(json.dumps(
        {"greedy": {"max_items": "99"}}))
    page, _ = render(data)
    check("a max_items value cannot exceed the hard budget",
          "Grab 6" in page and "Grab 7" not in page)

# Example widgets: shipped in briefing/widget-examples/, a folder the
# renderer never scans. They render only after a household copies one
# into a widgets root.
EXAMPLES = REPO / "briefing" / "widget-examples"
EXAMPLE_IDS = ("weekend-chores", "house-plants")

# The examples are not picked up by the renderer's own discovery scan,
# and a plain render shows neither of them.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    records = rb.discover_folder_widgets(
        str(data), rb.make_export_loader(str(data)))
    check("discovery scan does not pick up the example widgets",
          all(wid not in records for wid in EXAMPLE_IDS),
          ", ".join(sorted(records)))
    page, _ = render(data)
    check("a plain render shows neither example widget",
          "Weekend chores" not in page and "House plants" not in page
          and "Mow the front yard" not in page
          and "Tomatoes need water today." not in page)

# Both example manifests pass the renderer's own validator.
for wid in EXAMPLE_IDS:
    manifest = json.loads((EXAMPLES / wid / "widget.json").read_text())
    error = rb.validate_manifest(manifest, wid)
    check(f"example {wid} manifest passes the validator",
          error is None, str(error))

# Copied into a data directory's widgets folder, each example renders
# on the panel profile with its content visible.
with tempfile.TemporaryDirectory() as td:
    data, _ = make_case(Path(td))
    inside = data / "widgets"
    inside.mkdir()
    for wid in EXAMPLE_IDS:
        shutil.copytree(EXAMPLES / wid, inside / wid)
    page, err = render(data)
    check("copied examples render without warnings", err == "", err.strip())
    check("items example renders its heading and items",
          "<h2>Weekend chores</h2>" in page
          and "Mow the front yard" in page
          and "Stack the firewood" in page)
    check("status example renders its heading and lines",
          "<h2>House plants</h2>" in page
          and "Fern watered this morning." in page
          and "Tomatoes need water today." in page)

# The items example's declared max_items setting applies once copied:
# a settings.json value caps the list below its full length.
with tempfile.TemporaryDirectory() as td:
    data, _ = make_case(Path(td))
    inside = data / "widgets"
    inside.mkdir()
    shutil.copytree(EXAMPLES / "weekend-chores", inside / "weekend-chores")
    (data / "settings.json").write_text(json.dumps(
        {"weekend-chores": {"max_items": "3"}}))
    page, err = render(data)
    check("example max_items setting caps the copied widget",
          "Sweep the porch steps" in page
          and "Take the bins to the curb" not in page
          and "Stack the firewood" not in page)
    check("example setting applies without warnings",
          err == "", err.strip())

# Profile registry: profiles are data, defined once in the renderer.
# The validator, the render branches, and the CLI all read the
# registry, so these checks pin the registry itself.
check("PROFILES is the registry keys in order",
      rb.PROFILES == tuple(rb.PROFILE_REGISTRY))
for pname, pspec in rb.PROFILE_REGISTRY.items():
    check(f"profile {pname} declares size, colour, css, layout",
          isinstance(pspec["width"], int)
          and isinstance(pspec["height"], int)
          and pspec["colour"] in ("color", "mono")
          and pspec["layout"] in ("columns", "single")
          and f"width: {pspec['width']}px" in pspec["css"]
          and f"height: {pspec['height']}px" in pspec["css"])
    probe = {"id": "probe", "title": "Probe", "version": "1.0.0",
             "slot": "main", "order": 1, "profiles": [pname],
             "template": "items", "reads": []}
    check(f"validator accepts registry profile {pname}",
          rb.validate_manifest(probe, "probe") is None)

bad = {"id": "probe", "title": "Probe", "version": "1.0.0",
       "slot": "main", "order": 1, "profiles": ["watch"],
       "template": "items", "reads": []}
check("validator rejects a profile outside the registry",
      rb.validate_manifest(bad, "probe")
      == "profiles must be a subset of " + ", ".join(rb.PROFILES))

builtins = rb.builtin_widgets(rb.make_export_loader(str(SAMPLE)))
check("built in widgets declare exactly the registry profiles",
      all(w["manifest"]["profiles"] == list(rb.PROFILES)
          for w in builtins.values()))

source = MOD.read_text()
registry_block = source[source.index("PROFILE_REGISTRY = {"):
                        source.index("PROFILES = tuple(PROFILE_REGISTRY)")]
outside_registry = source.replace(registry_block, "")
check("no profile name is hardcoded outside the registry",
      '"kindle"' not in outside_registry
      and '"card"' not in outside_registry)

with tempfile.TemporaryDirectory() as td:
    data, _ = make_case(Path(td))
    for pname, pspec in rb.PROFILE_REGISTRY.items():
        page, err = render(data, profile=pname)
        check(f"sample data renders on profile {pname} with its css",
              pspec["css"] in page and "ifthe morning briefing" in page,
              err.strip())

# status lines never print None for missing counts (quality loop D-001)
sl = rb.status_lines({"down": ["AdGuard Home"]})
check("status lines with down services but no counts name the down services",
      bool(sl) and sl[0]["text"] == "Services down: AdGuard Home."
      and sl[0]["state"] == "warn")
sl = rb.status_lines({"services_up": 3, "services_total": 10, "down": ["Mealie"]})
check("status lines with counts keep the counted wording",
      bool(sl) and sl[0]["text"] == "3 of 10 services up. Down: Mealie.")
sl = rb.status_lines({"backup_last": "02:15", "backup_ok": True})
check("status lines with no counts and nothing down show only the backup line",
      [l["text"] for l in sl] == ["Backup ran at 02:15."])
sl = rb.status_lines({"services_total": 10})
check("status lines with a total and nothing down keep the all up wording",
      bool(sl) and sl[0]["text"] == "All 10 services up.")

# ---- Quality loop pass 2: sheet cases that were written, now executed ----

def probe_manifest(**over):
    manifest = {"id": "probe", "title": "Probe", "version": "1.0.0",
                "slot": "main", "order": 1, "profiles": ["panel"],
                "template": "items", "reads": []}
    manifest.update(over)
    return manifest


# Today section: all day label, the six event cap, the empty state.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "agenda.json").write_text(json.dumps({"date": "2026-11-21",
        "events": [{"time": "", "title": "Parade day", "all_day": True},
                   {"time": "9:00 AM", "title": "Dentist"}]}))
    page, _ = render(data)
    check("all day event renders the All day label",
          "All day" in section(page, "Today") and "Parade day" in page)

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "agenda.json").write_text(json.dumps({"events": [
        {"time": "9:00 AM", "title": f"Event {i}"} for i in range(1, 8)]}))
    page, _ = render(data)
    today = section(page, "Today")
    check("today section caps seven events at six rows",
          today.count("<li>") == 6 and "Event 6" in today
          and "Event 7" not in page)

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "agenda.json").write_text(json.dumps({"events": []}))
    page, _ = render(data)
    check("empty agenda renders the nothing on the calendar line",
          "Nothing on the calendar." in section(page, "Today"))

# Home section at render level: backup wording variants.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "status.json").write_text(json.dumps(
        {"services_up": 10, "services_total": 10, "down": [],
         "backup_last": "02:15", "backup_ok": False}))
    page, _ = render(data)
    check("backup not ok renders the needs a look line",
          "Backup needs a look at 02:15." in section(page, "Home"))

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "status.json").write_text(json.dumps(
        {"services_up": 10, "services_total": 10, "down": []}))
    page, _ = render(data)
    check("missing backup report renders the no backup line",
          "No backup report yet." in section(page, "Home"))

# Money section: missing budget, and the heading fallback.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "budget.json").unlink()
    page, _ = render(data)
    check("missing budget renders the no snapshot line",
          "No budget snapshot yet." in section(page, "Money"))

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "budget.json").write_text(json.dumps(
        {"lines": [{"label": "Left to spend", "value": "$5"}]}))
    page, _ = render(data)
    check("budget without a month uses the Money heading",
          "<h2>Money</h2>" in page
          and "Left to spend" in section(page, "Money"))

# List section: a missing list.json renders no section at all.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "list.json").unlink()
    page, _ = render(data)
    check("missing list renders no list section at all",
          "<h2>Shopping</h2>" not in page and "<h2>List</h2>" not in page
          and "Eggs" not in page)

# Lines shaping drops values that are not display text.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "typed-lines", title="Typed lines", template="lines",
                 data={"lines": [{"label": "Bool line", "value": True},
                                 {"label": {"nested": 1}, "value": "v"},
                                 {"label": "Good line", "value": "42"}]})
    page, _ = render(data)
    typed = section(page, "Typed lines")
    check("a line with a boolean value is dropped",
          "Bool line" not in page)
    check("a line with an object label is dropped",
          "Good line" in typed and typed.count("<li>") == 1)

# Discovery: the shared root renders, and a local widget overrides a
# shared widget with the same non reserved id.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    fake_root = Path(td) / "fake-briefing"
    for folder, title, item in (
            ("shared-one", "Shared one", "Shared one item"),
            ("override-me", "Shared title", "Shared version item")):
        wdir = fake_root / "widgets" / folder
        wdir.mkdir(parents=True)
        (wdir / "widget.json").write_text(json.dumps({
            "id": folder, "title": title, "version": "1.0.0",
            "slot": "main", "order": 60, "profiles": ["panel"],
            "template": "items", "reads": [],
        }))
        (wdir / "data.json").write_text(json.dumps({"items": [item]}))
    write_widget(widgets, "override-me", title="Local title", order=60,
                 data={"items": ["Local version item"]})
    old_file = rb.__file__
    rb.__file__ = str(fake_root / "render_briefing.py")
    try:
        page, err = render(data)
    finally:
        rb.__file__ = old_file
    check("a widget in the shared root renders",
          "Shared one item" in page)
    check("a local widget overrides a shared widget with the same id",
          "Local version item" in page
          and "Shared version item" not in page
          and "Local title" in page and "Shared title" not in page)

# Reads: own data wins over the export, generic exports are shaped to
# the allowed keys only, and an unreadable export warns by name.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "budget.json").write_text(json.dumps(
        {"month": "Testmonth",
         "lines": [{"label": "Export label", "value": "9"}]}))
    write_widget(widgets, "override-read", title="Override read",
                 template="lines", reads=["budget"],
                 data={"lines": [{"label": "Own label", "value": "1"}]})
    page, _ = render(data)
    own = section(page, "Override read")
    check("data.json keys override the declared export keys",
          "Own label" in own and "Export label" not in own)

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "notes.json").write_text(json.dumps(
        {"lines": [{"label": "L", "value": "V"}], "items": ["I"],
         "text": "Note text", "glance": "G", "title": "Note title",
         "secret": "SECRET", "other": "OTHER"}))
    resolved = rb.resolve_widget_data(
        {"reads": ["notes"], "template": "text"}, {},
        rb.make_export_loader(str(data)))
    check("a generic export passes only the shaped keys",
          set(resolved) == {"lines", "items", "text", "glance", "title"}
          and "secret" not in resolved and "other" not in resolved)

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "weather.json").write_text("{not json")
    write_widget(widgets, "weather-watcher", title="Weather watcher",
                 template="text", reads=["weather"])
    page, err = render(data)
    check("an unreadable export warns and the widget still renders",
          "warning: skipping unreadable export weather" in err
          and "Weather watcher" in page, err.strip())

# An oversize widget.json skips the widget, like oversize data does.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    big = {"id": "big-manifest", "title": "x" * 70000, "version": "1.0.0",
           "slot": "main", "order": 50, "profiles": ["panel"],
           "template": "items", "reads": []}
    write_widget(widgets, "big-manifest", raw_manifest=json.dumps(big))
    page, err = render(data)
    check("oversize widget.json skips the widget with a warning",
          "widget big-manifest: skipped" in err and "over 64 KB" in err,
          err.strip())

# validate_manifest reasons, called directly, one per broken field.
reason = rb.validate_manifest(probe_manifest(id="Bad Id"), "probe")
check("validator names the id for a bad id shape",
      reason is not None and "id" in reason, str(reason))
reason = rb.validate_manifest(probe_manifest(id="other"), "probe")
check("validator names the id and folder on a folder mismatch",
      reason is not None and "id" in reason and "folder" in reason,
      str(reason))
reason = rb.validate_manifest(probe_manifest(version="1.0"), "probe")
check("validator names the version for a bad version",
      reason is not None and "version" in reason, str(reason))
reason = rb.validate_manifest(probe_manifest(order=True), "probe")
check("validator names the order for a boolean order",
      reason is not None and "order" in reason, str(reason))
reason = rb.validate_manifest(
    probe_manifest(profiles=["panel", "panel"]), "probe")
check("validator names the profiles for duplicate profiles",
      reason is not None and "profiles" in reason, str(reason))
reason = rb.validate_manifest(probe_manifest(reads=["../secret"]), "probe")
check("validator names the reads for a bad reads name",
      reason is not None and "reads" in reason, str(reason))

# Settings declaration validation through validate_manifest.
reason = rb.validate_manifest(probe_manifest(settings=[
    {"key": "Bad Key", "type": "toggle", "label": "X"}]), "probe")
check("validator names the key for a bad setting key shape",
      reason is not None and "key" in reason, str(reason))
reason = rb.validate_manifest(probe_manifest(settings=[
    {"key": "ok_key", "type": "slider", "label": "X"}]), "probe")
check("validator names the type for an unknown setting type",
      reason is not None and "type" in reason, str(reason))
reason = rb.validate_manifest(probe_manifest(settings=[
    {"key": "pick", "type": "select", "label": "Pick",
     "options": ["a", "b"], "default": "c"}]), "probe")
check("validator names the default for a select default outside its options",
      reason is not None and "default" in reason and "options" in reason,
      str(reason))

# Status template: an unknown state renders as muted.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "weird-state", title="Weird state",
                 template="status", slot="side",
                 data={"lines": [{"text": "Weird state line",
                                  "state": "weird"}]})
    page, _ = render(data)
    check("an unknown status state is coerced to muted",
          '<p class="big muted">Weird state line</p>' in page)

# Text template: exactly at the budget is not cut.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "exact-text", title="Exact text", template="text",
                 data={"text": "y" * 220})
    page, _ = render(data)
    match = re.search(r"<h2>Exact text</h2><p class=\"big\">([^<]+)</p>",
                      page)
    out = html.unescape(match.group(1)) if match else ""
    check("text of exactly 220 characters is not cut",
          out == "y" * 220, f"len={len(out)}")

# Glance derivation with no glance key, one per template.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "glance-lines", title="Glance lines",
                 slot="glance", template="lines",
                 data={"lines": [{"label": "Water", "value": "2L"}]})
    write_widget(widgets, "glance-items", title="Glance items",
                 slot="glance", template="items",
                 data={"items": ["First thing", "Second thing"]})
    write_widget(widgets, "glance-status", title="Glance status",
                 slot="glance", template="status",
                 data={"lines": [{"text": "All systems go",
                                  "state": "ok"}]})
    write_widget(widgets, "glance-text", title="Glance text",
                 slot="glance", template="text",
                 data={"text": "Just a note"})
    page, _ = render(data)
    check("glance derives label colon value from a lines widget",
          '<p class="big">Water: 2L</p>' in page)
    check("glance derives the first item from an items widget",
          '<p class="big">First thing</p>' in page
          and "Second thing" not in page)
    check("glance derives the first line text from a status widget",
          '<p class="big">All systems go</p>' in page)
    check("glance derives the text from a text widget",
          '<p class="big">Just a note</p>' in page)

# A folder widget with no data at all renders its empty text.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "empty-widget", title="Empty widget",
                 template="text")
    page, _ = render(data)
    check("a folder widget with no data renders the no data line",
          "No data yet." in section(page, "Empty widget"))

# settings.json shapes: a non object top level is ignored with a
# warning; a non object per widget value counts as no supplied values.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "listed", title="Listed",
                 data={"items": ["Listed item"]})
    (data / "settings.json").write_text(json.dumps(["not", "an", "object"]))
    page, err = render(data)
    check("a non object settings.json is ignored with a warning",
          "Listed item" in page
          and "settings.json must hold an object" in err, err.strip())

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "per-widget", title="Per widget",
                 data={"items": [f"Pw {i}" for i in range(1, 6)]},
                 settings=[{"key": "max_items", "type": "select",
                            "label": "Show at most", "options": ["2", "6"],
                            "default": "2"}])
    (data / "settings.json").write_text(json.dumps({"per-widget": 42}))
    page, err = render(data)
    check("a non object per widget settings value counts as no values",
          "Pw 2" in page and "Pw 3" not in page and err == "",
          err.strip())

# Settings resolution: rejected values warn and fall back, per type.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "toggler", title="Toggler",
                 data={"items": ["Toggler item"]},
                 settings=[{"key": "show_title", "type": "toggle",
                            "label": "Show title", "default": True}])
    (data / "settings.json").write_text(json.dumps(
        {"toggler": {"show_title": "yes"}}))
    page, err = render(data)
    check("an invalid toggle value warns and falls back to the default",
          "widget toggler: setting show_title rejected, using default"
          in err and "<h2>Toggler</h2>" in page, err.strip())

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "numbered", title="Numbered",
                 data={"items": ["Numbered item"]},
                 settings=[{"key": "title", "type": "input",
                            "label": "Heading",
                            "default": "Default heading"}])
    (data / "settings.json").write_text(json.dumps(
        {"numbered": {"title": 42}}))
    page, err = render(data)
    check("a numeric value for an input setting is rejected with a warning",
          "widget numbered: setting title rejected, using default" in err
          and "<h2>Default heading</h2>" in page, err.strip())

# Custom settings: an invalid value warns; a valid one changes nothing.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "custom", title="Custom",
                 data={"items": ["Custom item"]},
                 settings=[{"key": "accent_color", "type": "input",
                            "label": "Accent", "default": "sage"}])
    (data / "settings.json").write_text(json.dumps(
        {"custom": {"accent_color": 42}}))
    page, err = render(data)
    check("an invalid value for a custom setting warns",
          "widget custom: setting accent_color rejected, using default"
          in err, err.strip())
    (data / "settings.json").write_text(json.dumps(
        {"custom": {"accent_color": "plum"}}))
    page_with, err_with = render(data)
    (data / "settings.json").unlink()
    page_without, _ = render(data)
    check("a valid custom setting value does not change the page",
          page_with == page_without and err_with == "", err_with.strip())

# layout.json shapes: a non list order warns, a non object file warns,
# and invalid order entries drop while valid ones still sort.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "layout.json").write_text(json.dumps({"order": "money"}))
    page, err = render(data)
    check("a non list layout order warns and is ignored",
          "layout: skipped, order must be a list of widget ids" in err
          and "Today" in page, err.strip())

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "layout.json").write_text(json.dumps(["money", "today"]))
    page, err = render(data)
    check("a non object layout.json warns and is ignored",
          "layout: skipped, layout.json must hold an object" in err
          and "Today" in page, err.strip())

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    (data / "layout.json").write_text(json.dumps(
        {"order": ["Bad Id", 42, "money", "today"]}))
    page, err = render(data, profile="kindle")
    check("invalid layout order entries are dropped, valid ones still sort",
          page.index("November") < page.index("Today") and err == "",
          err.strip())

# Failure isolation: no widget.json, and malformed data.json.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    bare = widgets / "no-manifest"
    bare.mkdir()
    (bare / "data.json").write_text(json.dumps({"items": ["Ghost item"]}))
    write_widget(widgets, "baddata", title="Bad data", template="items",
                 reads=["list"], data={"items": ["Placeholder"]})
    (widgets / "baddata" / "data.json").write_text("{oops")
    write_widget(widgets, "good2", title="Good two",
                 data={"items": ["Good two item"]})
    page, err = render(data)
    check("a widget folder with no widget.json is skipped with a warning",
          "widget no-manifest: skipped, no widget.json" in err,
          err.strip())
    check("a widget with malformed data.json is skipped whole",
          "widget baddata: skipped" in err and "bad data.json" in err
          and "Bad data" not in page and "Ghost item" not in page,
          err.strip())
    check("other widgets still render beside the failures",
          "Good two item" in page and "Today" in page)

# Code detection: the executable bit and a shebang both skip the folder.
with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    wdir = write_widget(widgets, "exec-note", title="Exec note",
                        data={"items": ["Should not render"]},
                        extra={"notes.txt": "plain notes\n"})
    (wdir / "notes.txt").chmod(0o755)
    page, err = render(data)
    check("a plain file with the executable bit set skips the folder",
          "Exec note" not in page
          and "widget exec-note: skipped" in err
          and "code file notes.txt" in err, err.strip())

with tempfile.TemporaryDirectory() as td:
    data, widgets = make_case(Path(td))
    write_widget(widgets, "shebang-note", title="Shebang note",
                 data={"items": ["Should not render"]},
                 extra={"data.txt": "#!/bin/sh\necho hi\n"})
    page, err = render(data)
    check("a file starting with a shebang skips the folder",
          "Shebang note" not in page
          and "widget shebang-note: skipped" in err
          and "code file data.txt" in err, err.strip())

passed = sum(1 for _, ok, _ in results if ok)
fails = [(n, d) for n, ok, d in results if not ok]
print(f"\nbriefing_widgets: {passed}/{len(results)} checks passed")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}"
          + (f"   [{d}]" if (not ok and d) else ""))
sys.exit(1 if fails else 0)
