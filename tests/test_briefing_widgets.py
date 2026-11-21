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

passed = sum(1 for _, ok, _ in results if ok)
fails = [(n, d) for n, ok, d in results if not ok]
print(f"\nbriefing_widgets: {passed}/{len(results)} checks passed")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}"
          + (f"   [{d}]" if (not ok and d) else ""))
sys.exit(1 if fails else 0)
