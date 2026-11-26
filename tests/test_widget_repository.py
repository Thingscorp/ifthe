#!/usr/bin/env python3
"""Hermetic tests for the widget repository tools:

  tools/ifthe-pack.py    install a pack into a widgets root
  tools/ifthe-index.py   build the three-record-kind index
  tools/ifthe-gate.py    the contribution gate (LIVE / REFUSED)

Fixtures are built from the repo's own example widgets
(briefing/widget-examples/: house-plants and weekend-chores), copied
into throwaway pack and source folders. The installed pack is then
rendered by the shipped renderer, imported here, never copied.
"""
import contextlib, hashlib, importlib.util, io, json, shutil, subprocess
import sys, tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK_TOOL = REPO / "tools" / "ifthe-pack.py"
INDEX_TOOL = REPO / "tools" / "ifthe-index.py"
GATE_TOOL = REPO / "tools" / "ifthe-gate.py"
MOD = REPO / "briefing" / "render_briefing.py"
SAMPLE = REPO / "briefing" / "sample-data"
EXAMPLES = REPO / "briefing" / "widget-examples"
spec = importlib.util.spec_from_file_location("render_briefing", MOD)
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)

NOW = datetime(2026, 11, 21, 7, 5)
WIDGETS = ["house-plants", "weekend-chores"]
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def run(tool, *args):
    return subprocess.run([sys.executable, str(tool), *[str(a) for a in args]],
                          capture_output=True, text=True)


def make_pack(base, version="1.0.0", widget_version=None, titles=None,
              widgets=WIDGETS, name="@test/morning-pack"):
    """Copy the example widgets into a pack folder under base."""
    pack = base / "morning-pack"
    pack.mkdir(parents=True, exist_ok=True)
    for wid in widgets:
        src = EXAMPLES / wid
        if src.exists():
            shutil.copytree(src, pack / wid)
            if widget_version or (titles and wid in titles):
                mpath = pack / wid / "widget.json"
                manifest = json.loads(mpath.read_text())
                if widget_version:
                    manifest["version"] = widget_version
                if titles and wid in titles:
                    manifest["title"] = titles[wid]
                mpath.write_text(json.dumps(manifest))
    (pack / "pack.json").write_text(json.dumps(
        {"name": name, "version": version, "widgets": list(widgets)}))
    return pack


def pack_checksum(pack_dir):
    digest = hashlib.sha256()
    paths = sorted(p.relative_to(pack_dir).as_posix()
                   for p in pack_dir.rglob("*") if p.is_file())
    for rel in paths:
        digest.update((pack_dir / rel).read_bytes())
    return digest.hexdigest()


# --- ifthe-pack: install, render, refuse, upgrade --------------------
with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    pack = make_pack(base / "src")
    data_dir = base / "data"
    data_dir.mkdir()
    for name in ("agenda", "status", "budget", "list"):
        shutil.copyfile(SAMPLE / f"{name}.json", data_dir / f"{name}.json")
    root = data_dir / "widgets"

    proc = run(PACK_TOOL, "install", pack, root)
    check("pack install exits clean", proc.returncode == 0, proc.stderr.strip())
    check("pack summary line names the pack, version and count",
          proc.stdout.strip()
          == "pack @test/morning-pack 1.0.0: 2 widgets installed",
          proc.stdout.strip())
    check("both widget folders landed in the widgets root",
          sorted(p.name for p in root.iterdir()) == WIDGETS)

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        page = rb.render(str(data_dir), now=NOW, profile="panel")
    check("installed widgets render in the panel briefing",
          "<h2>House plants</h2>" in page and "<h2>Weekend chores</h2>" in page,
          err.getvalue().strip())
    check("rendering the installed pack warns about nothing",
          err.getvalue() == "", err.getvalue().strip())

    proc = run(PACK_TOOL, "install", pack, root)
    check("reinstalling the same versions is refused, naming the widget",
          proc.returncode == 1 and "house-plants" in proc.stderr
          and "not higher" in proc.stderr, proc.stderr.strip())

    older = make_pack(base / "old", widget_version="0.9.0")
    proc = run(PACK_TOOL, "install", older, root)
    check("a downgrade is refused, naming the widget",
          proc.returncode == 1 and "house-plants" in proc.stderr
          and "0.9.0" in proc.stderr, proc.stderr.strip())
    installed = json.loads((root / "house-plants" / "widget.json").read_text())
    check("the refused downgrade changed nothing",
          installed["version"] == "1.0.0")

    newer = make_pack(base / "new", widget_version="1.1.0",
                      titles={"house-plants": "House plants, watered"})
    proc = run(PACK_TOOL, "install", newer, root)
    installed = json.loads((root / "house-plants" / "widget.json").read_text())
    check("a higher version replaces the installed widget",
          proc.returncode == 0 and installed["version"] == "1.1.0"
          and installed["title"] == "House plants, watered",
          proc.stderr.strip())

# --- ifthe-pack: a bad pack installs nothing --------------------------
with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    root = base / "widgets"

    ghost = make_pack(base / "ghost", widgets=["house-plants", "ghost-widget"])
    proc = run(PACK_TOOL, "install", ghost, root)
    check("a pack listing a missing widget folder is refused by name",
          proc.returncode == 1 and "ghost-widget" in proc.stderr
          and "no folder in the pack" in proc.stderr, proc.stderr.strip())
    check("the refused pack installed nothing",
          not root.exists() or not any(root.iterdir()))

    mismatch = base / "mismatch"
    (mismatch / "renamed-plants").mkdir(parents=True)
    shutil.copytree(EXAMPLES / "house-plants", mismatch / "renamed-plants",
                    dirs_exist_ok=True)
    (mismatch / "pack.json").write_text(json.dumps(
        {"name": "@test/mismatch", "version": "1.0.0",
         "widgets": ["renamed-plants"]}))
    proc = run(PACK_TOOL, "install", mismatch, root)
    check("a widget whose id does not match its folder is refused by name",
          proc.returncode == 1 and "renamed-plants" in proc.stderr
          and "does not match" in proc.stderr, proc.stderr.strip())
    check("the mismatched pack installed nothing",
          not root.exists() or not any(root.iterdir()))

# --- ifthe-pack: bad name, bad version, broken pack.json, broken install --
with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    root = base / "widgets"

    bad_name = make_pack(base / "badname", name="morning-pack")
    proc = run(PACK_TOOL, "install", bad_name, root)
    check("a pack name outside the scoped pattern is refused, naming it",
          proc.returncode == 1
          and "pack name must be a scoped name" in proc.stderr,
          proc.stderr.strip())
    check("the badly named pack installed nothing",
          not root.exists() or not any(root.iterdir()))

    bad_version = make_pack(base / "badver", version="1.0")
    proc = run(PACK_TOOL, "install", bad_version, root)
    check("a pack version that is not major.minor.patch is refused",
          proc.returncode == 1
          and "pack version must be major.minor.patch" in proc.stderr,
          proc.stderr.strip())
    check("the badly versioned pack installed nothing",
          not root.exists() or not any(root.iterdir()))

    broken = make_pack(base / "broken")
    (broken / "pack.json").write_text("{not json")
    proc = run(PACK_TOOL, "install", broken, root)
    lines = [l for l in proc.stderr.splitlines() if l.strip()]
    check("a malformed pack.json is refused with one error line",
          proc.returncode == 1 and len(lines) == 1
          and lines[0].startswith("error:"), proc.stderr.strip())
    check("the broken pack installed nothing",
          not root.exists() or not any(root.iterdir()))

    good = make_pack(base / "good")
    proc = run(PACK_TOOL, "install", good, root)
    check("the good pack installs before its copy is broken",
          proc.returncode == 0, proc.stderr.strip())
    (root / "house-plants" / "widget.json").unlink()
    proc = run(PACK_TOOL, "install", good, root)
    check("an installed copy with no widget.json refuses, naming the widget",
          proc.returncode == 1 and "house-plants" in proc.stderr
          and "installed copy has no widget.json" in proc.stderr,
          proc.stderr.strip())

    root2 = base / "widgets2"
    proc = run(PACK_TOOL, "install", good, root2)
    (root2 / "house-plants" / "widget.json").write_text("{oops")
    proc = run(PACK_TOOL, "install", good, root2)
    check("an unreadable installed widget.json refuses, naming the widget",
          proc.returncode == 1 and "house-plants" in proc.stderr
          and "installed copy" in proc.stderr, proc.stderr.strip())

# --- ifthe-index: three record kinds, invalid widget skipped ----------
with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    source = base / "source"
    source.mkdir()
    shutil.copytree(EXAMPLES / "weekend-chores", source / "weekend-chores")
    pack = make_pack(source)
    broken = source / "broken-widget"
    broken.mkdir()
    (broken / "widget.json").write_text(json.dumps(
        {"id": "broken-widget", "title": "Broken", "version": "1.0.0",
         "slot": "main", "order": 10, "profiles": ["panel"],
         "template": "hologram", "reads": []}))
    out = base / "index.json"
    proc = run(INDEX_TOOL, "build", source, out)
    check("index build exits clean despite the broken widget",
          proc.returncode == 0, proc.stderr.strip())
    check("index summary counts listings, assets and releases",
          proc.stdout.strip() == "index: 2 listings, 2 assets, 1 releases",
          proc.stdout.strip())
    check("the broken widget is skipped with a named warning",
          "warning: widget broken-widget: skipped, unknown template hologram"
          in proc.stderr, proc.stderr.strip())
    index = json.loads(out.read_text()) if out.exists() else {}
    check("the index holds exactly the three record kinds",
          sorted(index) == ["assets", "listings", "releases"],
          ", ".join(sorted(index)))
    listings = {l["id"]: l for l in index.get("listings", [])}
    check("standalone and pack widgets are listed once each",
          sorted(listings) == WIDGETS, ", ".join(sorted(listings)))
    check("a listing carries title, author and zeroed counters",
          listings.get("house-plants", {}).get("title") == "House plants"
          and listings.get("house-plants", {}).get("author")
          == "ifthe examples"
          and listings.get("house-plants", {}).get("installs") == 0
          and listings.get("house-plants", {}).get("likes") == 0)
    assets = {a["id"]: a for a in index.get("assets", [])}
    check("assets take the description from the README's first line",
          assets.get("house-plants", {}).get("description") == "House plants",
          str(assets.get("house-plants")))
    check("previews are keyed by the profiles the widget declares",
          sorted(assets.get("house-plants", {}).get("previews", {}))
          == ["card", "kindle", "panel"])
    releases = index.get("releases", [])
    check("one release per pack, with the declared widget ids",
          len(releases) == 1
          and releases[0].get("name") == "@test/morning-pack"
          and releases[0].get("version") == "1.0.0"
          and releases[0].get("widgets") == WIDGETS,
          str(releases))
    check("the release checksum is the pack's SHA-256 in path order",
          len(releases) == 1
          and releases[0].get("checksum") == pack_checksum(pack),
          releases[0].get("checksum", "") if releases else "")

# --- ifthe-index: missing source, no README, malformed pack -----------
with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    out = base / "index.json"
    proc = run(INDEX_TOOL, "build", base / "no-such-folder", out)
    lines = [l for l in proc.stderr.splitlines() if l.strip()]
    check("index build on a missing source folder fails with one error line",
          proc.returncode == 1 and len(lines) == 1
          and lines[0].startswith("error:")
          and "no source folder" in lines[0], proc.stderr.strip())

    source = base / "source"
    source.mkdir()
    shutil.copytree(EXAMPLES / "weekend-chores", source / "weekend-chores")
    (source / "weekend-chores" / "README.md").unlink()
    proc = run(INDEX_TOOL, "build", source, out)
    index = json.loads(out.read_text()) if out.exists() else {}
    assets = {a["id"]: a for a in index.get("assets", [])}
    check("a widget with no README gets a null description",
          proc.returncode == 0
          and "weekend-chores" in assets
          and assets["weekend-chores"].get("description") is None,
          proc.stderr.strip())

    source2 = base / "source2"
    bad_pack = source2 / "bad-pack"
    bad_pack.mkdir(parents=True)
    shutil.copytree(EXAMPLES / "house-plants", bad_pack / "house-plants")
    (bad_pack / "pack.json").write_text("{oops")
    out2 = base / "index2.json"
    proc = run(INDEX_TOOL, "build", source2, out2)
    index = json.loads(out2.read_text()) if out2.exists() else {}
    check("a malformed pack warns and yields no release or listings",
          proc.returncode == 0
          and "warning: pack bad-pack: skipped" in proc.stderr
          and index.get("releases") == [] and index.get("listings") == []
          and index.get("assets") == [], proc.stderr.strip())

# --- ifthe-gate: LIVE for the examples, REFUSED with reasons ----------
for wid in WIDGETS:
    proc = run(GATE_TOOL, "check", EXAMPLES / wid)
    check(f"gate returns LIVE for the {wid} example",
          proc.returncode == 0 and proc.stdout.strip() == f"LIVE: {wid}",
          proc.stdout.strip() + proc.stderr.strip())

with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    coded = base / "house-plants"
    shutil.copytree(EXAMPLES / "house-plants", coded)
    (coded / "app.py").write_text("print('not data')\n")
    proc = run(GATE_TOOL, "check", coded)
    check("gate refuses a folder holding a code file, naming it",
          proc.returncode == 1
          and proc.stdout.strip() == "REFUSED: folder holds code file app.py",
          proc.stdout.strip())

    half = base / "half-widget"
    half.mkdir()
    (half / "widget.json").write_text(json.dumps({"id": "half-widget"}))
    proc = run(GATE_TOOL, "check", half)
    check("gate refuses a broken manifest, naming the first failed check",
          proc.returncode == 1
          and proc.stdout.strip() == "REFUSED: missing required field title",
          proc.stdout.strip())

# --- ifthe-gate: no folder, bad usage, oversize data, shebang ---------
with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    proc = run(GATE_TOOL, "check", base / "no-such-widget")
    check("gate refuses a path that is not a folder",
          proc.returncode == 1
          and proc.stdout.strip().startswith("REFUSED: no folder"),
          proc.stdout.strip())

    for args in ((), ("check",), ("peek", EXAMPLES / "house-plants")):
        proc = run(GATE_TOOL, *args)
        check(f"gate with wrong arguments {args} exits 1 with no verdict",
              proc.returncode == 1 and "LIVE" not in proc.stdout
              and "REFUSED" not in proc.stdout,
              proc.stdout.strip() + proc.stderr.strip())

    fat = base / "house-plants"
    shutil.copytree(EXAMPLES / "house-plants", fat)
    (fat / "data.json").write_text(json.dumps({"text": "x" * 70000}))
    proc = run(GATE_TOOL, "check", fat)
    check("gate refuses a widget whose data.json is over 64 KB",
          proc.returncode == 1
          and proc.stdout.strip() == "REFUSED: data.json is over 64 KB",
          proc.stdout.strip())

    scripted = base / "weekend-chores"
    shutil.copytree(EXAMPLES / "weekend-chores", scripted)
    (scripted / "notes.txt").write_text("#!/bin/sh\necho not data\n")
    proc = run(GATE_TOOL, "check", scripted)
    check("gate refuses a folder holding a file that starts with a shebang",
          proc.returncode == 1
          and proc.stdout.strip()
          == "REFUSED: folder holds code file notes.txt",
          proc.stdout.strip())

passed = sum(1 for _, ok, _ in results if ok)
print(f"\nwidget repository: {passed}/{len(results)} checks passed")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}"
          + (f"   [{d}]" if (not ok and d) else ""))
sys.exit(1 if any(not ok for _, ok, _ in results) else 0)
