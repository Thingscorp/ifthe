#!/usr/bin/env python3
"""Hermetic tests for tools/pebble2ifthe.py, the Pebble to ifthe converter.

The worked example is built from the Clay project's own serialize
fixture config (test/spec/lib/clay-config.js in the Clay source: an
input, a select, a toggle, a checkboxgroup and a slider), extended
with a radiogroup, a color item, layout and form items, one undeclared
key, and a package.json whose messageKeys declare only a subset of
the fixture's keys plus the extra ones the test names.
"""
import contextlib, importlib.util, io, json, re, shutil, subprocess, sys
import tempfile, time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools" / "pebble2ifthe.py"
MOD = REPO / "briefing" / "render_briefing.py"
SAMPLE = REPO / "briefing" / "sample-data"
spec = importlib.util.spec_from_file_location("render_briefing", MOD)
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)

NOW = datetime(2026, 11, 21, 7, 5)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


# The worked example input: the Clay serialize fixture config, extended.
CLAY_CONFIG = [
    {"type": "section", "items": [
        {"type": "heading", "defaultValue": "Example header"},
        {"type": "input", "messageKey": "user_name",
         "label": "User name", "defaultValue": "Jane"},
        {"type": "select", "messageKey": "flavor",
         "label": "Favorite flavor", "defaultValue": "grape",
         "options": [{"label": "Berry", "value": "berry"},
                     {"label": "Grape", "value": "grape"}]},
    ]},
    {"type": "toggle", "messageKey": "enableAnimations",
     "label": "Enable animations", "defaultValue": True},
    {"type": "radiogroup", "messageKey": "favorite_food",
     "label": "Favorite food", "defaultValue": "pizza",
     "options": [{"label": "Sushi", "value": "sushi"},
                 {"label": "Pizza", "value": "pizza"}]},
    {"type": "checkboxgroup", "messageKey": "toppings",
     "label": "Toppings", "options": ["Sushi", "Pizza"],
     "defaultValue": [True, False]},
    {"type": "slider", "messageKey": "rating", "label": "Rating",
     "step": 0.05, "defaultValue": 12.5},
    {"type": "color", "messageKey": "background",
     "label": "Background color", "defaultValue": "ff0000"},
    {"type": "input", "messageKey": "secret_key", "label": "Secret"},
    {"type": "text", "defaultValue": "Example text item."},
    {"type": "submit", "defaultValue": "Save"},
]

PACKAGE = {
    "name": "clay-example",
    "version": "1.0",
    "author": "Test",
    "pebble": {
        "displayName": "Clay Example",
        "enableMultiJS": True,
        # A subset of the config's keys, plus toppings, rating and
        # background (declared but unmappable), plus one key with no
        # Clay item at all. secret_key is deliberately not declared.
        "messageKeys": ["user_name", "flavor", "enableAnimations",
                        "favorite_food", "toppings", "rating",
                        "background", "unused_key"],
    },
}


def run_tool(input_dir, output_dir):
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(input_dir), str(output_dir)],
        capture_output=True, text=True)
    return proc, time.perf_counter() - start


def run_args(*args):
    return subprocess.run(
        [sys.executable, str(TOOL), *[str(a) for a in args]],
        capture_output=True, text=True)


def convert_case(base, package, clay):
    """Write one converter input under base and run the tool on it.

    package and clay are dumped as JSON, or written raw when given as
    strings; either may be None to leave the file out. Returns
    (proc, manifest, data), with manifest and data read back from the
    single widget folder the tool wrote, or empty dicts when it wrote
    none.
    """
    src = base / "input"
    src.mkdir(parents=True, exist_ok=True)
    if package is not None:
        text = package if isinstance(package, str) else json.dumps(package)
        (src / "package.json").write_text(text)
    if clay is not None:
        text = clay if isinstance(clay, str) else json.dumps(clay)
        (src / "config.json").write_text(text)
    out = base / "output"
    proc = run_args(src, out)
    manifest, data = {}, {}
    folders = [p for p in out.iterdir() if p.is_dir()] if out.exists() else []
    if len(folders) == 1:
        manifest = json.loads((folders[0] / "widget.json").read_text())
        data = json.loads((folders[0] / "data.json").read_text())
    return proc, manifest, data


def mini_package(**pebble_overrides):
    pebble = {"displayName": "Mini", "messageKeys": ["user_name"]}
    pebble.update(pebble_overrides)
    return {"name": "mini", "version": "1.0", "pebble": pebble}


with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    src = base / "input"
    src.mkdir()
    (src / "package.json").write_text(json.dumps(PACKAGE))
    (src / "config.json").write_text(json.dumps(CLAY_CONFIG))
    out = base / "output"
    proc, elapsed = run_tool(src, out)
    stdout = proc.stdout
    print(f"conversion time for the worked example: {elapsed:.3f}s")
    check("converter exits clean on the worked example",
          proc.returncode == 0, proc.stderr.strip())
    folders = [p for p in out.iterdir() if p.is_dir()] if out.exists() else []
    check("converter writes exactly one widget folder", len(folders) == 1)
    widget_dir = folders[0] if folders else base / "missing"
    files = sorted(p.name for p in widget_dir.iterdir()) \
        if widget_dir.exists() else []
    check("output is data only: widget.json and data.json",
          files == ["data.json", "widget.json"], ", ".join(files))
    manifest = json.loads((widget_dir / "widget.json").read_text()) \
        if "widget.json" in files else {}
    data = json.loads((widget_dir / "data.json").read_text()) \
        if "data.json" in files else {}

    wid = manifest.get("id", "")
    check("widget id is generated from the package name with a suffix",
          wid.startswith("clay-example-") and rb.ID_RE.match(wid) is not None,
          wid)
    check("widget id is stable across runs",
          run_tool(src, base / "output2")[0].returncode == 0
          and (base / "output2" / wid / "widget.json").exists())
    check("displayName becomes the widget title",
          manifest.get("title") == "Clay Example")
    check("package version 1.0 normalizes to 1.0.0",
          manifest.get("version") == "1.0.0")

    error = rb.validate_manifest(manifest, widget_dir.name)
    check("converted manifest passes the shipped renderer validator",
          error is None, str(error))

    settings = {s["key"]: s for s in manifest.get("settings", [])}
    check("only renderer-honoured types become settings",
          sorted(settings) == ["enable_animations", "favorite_food",
                               "flavor", "user_name"],
          ", ".join(sorted(settings)))
    check("camelCase messageKey normalizes to a snake_case setting key",
          settings.get("enable_animations", {}).get("type") == "toggle")
    check("radiogroup becomes a select with the option values",
          settings.get("favorite_food", {}).get("type") == "select"
          and settings.get("favorite_food", {}).get("options")
          == ["sushi", "pizza"])
    check("Clay defaultValue becomes the setting default",
          settings.get("flavor", {}).get("default") == "grape"
          and settings.get("user_name", {}).get("default") == "Jane"
          and settings.get("enable_animations", {}).get("default") is True)

    check("defaults land in data.json for converted keys",
          data.get("user_name") == "Jane" and data.get("flavor") == "grape"
          and data.get("enable_animations") is True
          and data.get("favorite_food") == "pizza")
    check("declared but unmappable keys keep their Clay default in data.json",
          data.get("toppings") == [True, False]
          and data.get("rating") == 12.5
          and data.get("background") == "ff0000")
    check("a declared key with no Clay item appears in data.json as null",
          "unused_key" in data and data.get("unused_key") is None)
    check("the undeclared key is nowhere in the output",
          "secret_key" not in data and "secret_key" not in settings)

    check("the undeclared item is reported by name and dropped",
          "dropped: secret_key (input)" in stdout
          and "not declared" in stdout, stdout.strip())
    check("unsupported types are reported with the renderer reason",
          "dropped: rating (slider)" in stdout
          and "dropped: background (color)" in stdout
          and "dropped: toppings (checkboxgroup)" in stdout
          and "no setting type" in stdout, stdout.strip())
    check("layout and form items are reported and dropped",
          "dropped: Example header (heading)" in stdout
          and "dropped: Example text item. (text)" in stdout
          and "dropped: Save (submit)" in stdout, stdout.strip())
    summary = stdout.strip().splitlines()[-1] if stdout.strip() else ""
    check("the summary line names the id, settings and dropped counts",
          summary == f"widget {wid}: 4 settings, 8 dropped", summary)

    # The converted widget renders in a briefing at the panel profile.
    data_dir = base / "data"
    data_dir.mkdir()
    for name in ("agenda", "status", "budget", "list"):
        shutil.copyfile(SAMPLE / f"{name}.json", data_dir / f"{name}.json")
    beside = base / "widgets"
    beside.mkdir()
    shutil.copytree(widget_dir, beside / wid)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        page = rb.render(str(data_dir), now=NOW, profile="panel")
    check("converted widget renders in the panel briefing",
          "<h2>Clay Example</h2>" in page, err.getvalue().strip())
    check("rendering the converted widget warns about nothing",
          err.getvalue() == "", err.getvalue().strip())

# Key shapes and Clay corners the worked example does not reach.
with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    proc = run_args()
    lines = [l for l in proc.stderr.splitlines() if l.strip()]
    check("running with no arguments fails with one usage line",
          proc.returncode != 0 and len(lines) == 1
          and lines[0].startswith("error:"), proc.stderr.strip())

    scoped = mini_package()
    scoped["name"] = "@scope/name"
    proc, manifest, _ = convert_case(base / "scoped", scoped, [
        {"type": "input", "messageKey": "user_name", "defaultValue": "Jo"}])
    check("a scoped package name yields an id from the name part only",
          proc.returncode == 0
          and manifest.get("id", "").startswith("name-"),
          manifest.get("id", ""))

    long_version = mini_package()
    long_version["version"] = "1.0.0.0"
    proc, manifest, _ = convert_case(base / "longver", long_version, [
        {"type": "input", "messageKey": "user_name", "defaultValue": "Jo"}])
    check("version 1.0.0.0 normalizes to 1.0.0",
          manifest.get("version") == "1.0.0", manifest.get("version", ""))
    numeric_version = mini_package()
    numeric_version["version"] = 2
    proc, manifest, _ = convert_case(base / "numver", numeric_version, [
        {"type": "input", "messageKey": "user_name", "defaultValue": "Jo"}])
    check("a non-string version falls back to 1.0.0",
          manifest.get("version") == "1.0.0", manifest.get("version", ""))

    proc, manifest, data = convert_case(
        base / "dictkeys",
        mini_package(messageKeys={"user_name": {}, "flavor": {}}),
        [{"type": "input", "messageKey": "user_name", "defaultValue": "Jo"},
         {"type": "select", "messageKey": "flavor", "defaultValue": "grape",
          "options": [{"label": "Grape", "value": "grape"}]}])
    settings = {s["key"]: s for s in manifest.get("settings", [])}
    check("messageKeys in object form declares the same keys as list form",
          proc.returncode == 0
          and sorted(settings) == ["flavor", "user_name"]
          and data.get("user_name") == "Jo" and data.get("flavor") == "grape",
          proc.stderr.strip())

    proc, manifest, data = convert_case(
        base / "arraykey", mini_package(messageKeys=["food[3]"]),
        [{"type": "toggle", "messageKey": "food[3]", "defaultValue": True}])
    settings = {s["key"]: s for s in manifest.get("settings", [])}
    check("an array suffix on a messageKey collapses to the base key",
          proc.returncode == 0 and sorted(settings) == ["food"]
          and data.get("food") is True, proc.stderr.strip())

    proc, manifest, data = convert_case(
        base / "dupe", mini_package(),
        [{"type": "toggle", "messageKey": "user_name", "defaultValue": True},
         {"type": "toggle", "messageKey": "user_name", "defaultValue": False}])
    settings = {s["key"]: s for s in manifest.get("settings", [])}
    check("a second item claiming a converted key is dropped and reported",
          proc.returncode == 0 and len(settings) == 1
          and data.get("user_name") is True
          and "dropped: user_name (toggle)" in proc.stdout
          and "already converted" in proc.stdout, proc.stdout.strip())

    proc, manifest, _ = convert_case(
        base / "optgroups", mini_package(messageKeys=["flavor"]),
        [{"type": "select", "messageKey": "flavor", "defaultValue": "lime",
          "options": [
              {"label": "Citrus", "value": [
                  {"label": "Lemon", "value": "lemon"},
                  {"label": "Lime", "value": "lime"}]},
              {"label": "Cola", "value": "cola"}]}])
    settings = {s["key"]: s for s in manifest.get("settings", [])}
    check("optgroups flatten to the leaf option values",
          settings.get("flavor", {}).get("options")
          == ["lemon", "lime", "cola"]
          and settings.get("flavor", {}).get("default") == "lime",
          str(settings.get("flavor")))

    proc, manifest, data = convert_case(
        base / "nooptions", mini_package(messageKeys=["flavor"]),
        [{"type": "select", "messageKey": "flavor", "defaultValue": "grape",
          "options": []}])
    settings = {s["key"]: s for s in manifest.get("settings", [])}
    check("a select with no usable options is dropped, default kept in data",
          proc.returncode == 0 and "flavor" not in settings
          and "dropped: flavor (select)" in proc.stdout
          and "no usable options" in proc.stdout
          and data.get("flavor") == "grape", proc.stdout.strip())

    proc, manifest, _ = convert_case(
        base / "nested", mini_package(),
        [{"type": "section", "items": [
            {"type": "section", "items": [
                {"type": "toggle", "messageKey": "user_name",
                 "defaultValue": True}]}]}])
    settings = {s["key"]: s for s in manifest.get("settings", [])}
    check("sections nested in sections flatten and their items convert",
          proc.returncode == 0
          and settings.get("user_name", {}).get("type") == "toggle"
          and "layout only" in proc.stdout, proc.stdout.strip())

    proc, manifest, data = convert_case(
        base / "checkbox", mini_package(messageKeys=["toppings"]),
        [{"type": "checkboxgroup", "messageKey": "toppings",
          "options": ["Sushi", "Pizza", "Extra cheese"]}])
    settings = {s["key"]: s for s in manifest.get("settings", [])}
    check("a checkboxgroup with no default yields one false per option",
          proc.returncode == 0 and "toppings" not in settings
          and data.get("toppings") == [False, False, False],
          str(data.get("toppings")))

# Input errors: each exits 1 with exactly one error line.
with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    def expect_one_error(name, sub, package, clay):
        proc, _, _ = convert_case(base / sub, package, clay)
        lines = [l for l in proc.stderr.splitlines() if l.strip()]
        check(name, proc.returncode == 1 and len(lines) == 1
              and lines[0].startswith("error:"), proc.stderr.strip())

    expect_one_error("package.json that is not an object fails with one line",
                     "notobject", "[1, 2]", [])
    expect_one_error("package.json with no pebble object fails with one line",
                     "nopebble", {"name": "mini", "version": "1.0"}, [])
    expect_one_error("messageKeys of a wrong type fails with one error line",
                     "badkeys", mini_package(messageKeys="user_name"), [])
    expect_one_error("no Clay config under any accepted name fails plainly",
                     "noclay", mini_package(), None)
    expect_one_error("a Clay config that is not an array fails with one line",
                     "badclay", mini_package(), {"not": "an array"})

# Bad input: one plain error line, nonzero exit.
with tempfile.TemporaryDirectory() as td:
    proc, _ = run_tool(Path(td) / "empty", Path(td) / "out")
    lines = [l for l in proc.stderr.splitlines() if l.strip()]
    check("missing input folder fails with one error line",
          proc.returncode != 0 and len(lines) == 1
          and lines[0].startswith("error:"), proc.stderr.strip())

passed = sum(1 for _, ok, _ in results if ok)
print(f"\npebble2ifthe: {passed}/{len(results)} checks passed")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}"
          + (f"   [{d}]" if (not ok and d) else ""))
sys.exit(1 if any(not ok for _, ok, _ in results) else 0)
