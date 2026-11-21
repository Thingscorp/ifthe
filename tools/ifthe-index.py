#!/usr/bin/env python3
"""Build the ifthe widget index from a folder of published widgets.

Reads a source folder holding published widget folders and pack
folders (a folder with a pack.json is a pack; a folder with a
widget.json is a widget; anything else is ignored) and writes one
JSON file with the three record kinds fixed in briefing/WIDGETS.md,
"The index", kept separate:

  listings   one per widget: id, title, author, category, and the
             counters installs and likes, both starting at 0.
  assets     one per listing: a description (the widget README's
             first line, when the widget carries one) and a previews
             object keyed by profile, one entry per profile the
             widget declares.
  releases   one per pack: name, version, the widget ids the pack
             declares, and a checksum: the SHA-256 of the pack's
             files, fed in sorted path order.

Widgets inside a pack are published widgets too, so they get
listings alongside standalone ones; a widget id listed twice is
indexed once. A widget folder the renderer itself would skip (a code
file in the folder, an unreadable or oversize widget.json, a
manifest that fails the renderer's own validate_manifest) is skipped
with one warning line to stderr naming the widget and the reason,
never included and never fatal. A pack whose pack.json is malformed
loses its release the same way.

Data only: the tool reads folders and writes one JSON file. No
network, no state. Standard library only. The last line of stdout is
the summary: listings, assets and releases counts.

  python3 tools/ifthe-index.py build SOURCE_DIR OUT_FILE
"""
import hashlib, importlib.util, json, os, sys


class IndexError(Exception):
    pass


def load_renderer():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "briefing", "render_briefing.py")
    spec = importlib.util.spec_from_file_location("render_briefing", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path, label):
    try:
        with open(path) as fh:
            return json.load(fh)
    except OSError as exc:
        raise IndexError(f"cannot read {label}: {exc.strerror or exc}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndexError(f"bad {label}: {exc}")


def valid_manifest(rb, widget_dir, folder_name, warnings):
    """The renderer's own acceptance checks, in the renderer's order.

    Return the manifest, or None after appending one warning line.
    """
    code = rb.folder_code_file(widget_dir)
    if code is not None:
        warnings.append(
            f"widget {folder_name}: skipped, folder holds code file {code}")
        return None
    manifest, error = rb.read_widget_file(
        os.path.join(widget_dir, "widget.json"), folder_name, "widget.json")
    if error is not None:
        warnings.append(f"widget {folder_name}: skipped, {error}")
        return None
    error = rb.validate_manifest(manifest, folder_name)
    if error is not None:
        warnings.append(f"widget {folder_name}: skipped, {error}")
        return None
    return manifest


def description(widget_dir):
    path = os.path.join(widget_dir, "README.md")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip().lstrip("#").strip()
                if line:
                    return line
    except (OSError, UnicodeDecodeError):
        return None
    return None


def add_listing(rb, widget_dir, folder_name, listings, assets, warnings):
    manifest = valid_manifest(rb, widget_dir, folder_name, warnings)
    if manifest is None:
        return
    wid = manifest["id"]
    if wid in listings:
        return
    listings[wid] = {
        "id": wid,
        "title": manifest["title"],
        "author": manifest.get("author"),
        "category": manifest.get("category"),
        "installs": 0,
        "likes": 0,
    }
    assets[wid] = {
        "id": wid,
        "description": description(widget_dir),
        "previews": {profile: True for profile in manifest["profiles"]},
    }


def pack_checksum(pack_dir):
    digest = hashlib.sha256()
    paths = []
    for root, dirs, files in os.walk(pack_dir):
        dirs.sort()
        for filename in files:
            paths.append(os.path.relpath(os.path.join(root, filename),
                                         pack_dir))
    for rel in sorted(paths):
        with open(os.path.join(pack_dir, rel), "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
    return digest.hexdigest()


def add_pack(rb, pack_dir, folder_name, listings, assets, releases, warnings):
    try:
        pack = load_json(os.path.join(pack_dir, "pack.json"), "pack.json")
    except IndexError as exc:
        warnings.append(f"pack {folder_name}: skipped, {exc}")
        return
    name = pack.get("name") if isinstance(pack, dict) else None
    version = pack.get("version") if isinstance(pack, dict) else None
    widgets = pack.get("widgets") if isinstance(pack, dict) else None
    if not isinstance(name, str) or not name \
            or not isinstance(version, str) \
            or not rb.VERSION_RE.match(version) \
            or not isinstance(widgets, list) \
            or any(not isinstance(w, str) for w in widgets):
        warnings.append(
            f"pack {folder_name}: skipped, pack.json needs a name, "
            "a major.minor.patch version and a widgets list")
        return
    releases[name] = {
        "name": name,
        "version": version,
        "widgets": list(widgets),
        "checksum": pack_checksum(pack_dir),
    }
    for wid in widgets:
        widget_dir = os.path.join(pack_dir, wid)
        if os.path.isdir(widget_dir):
            add_listing(rb, widget_dir, wid, listings, assets, warnings)


def build(source_dir):
    if not os.path.isdir(source_dir):
        raise IndexError(f"no source folder {source_dir}")
    rb = load_renderer()
    listings, assets, releases, warnings = {}, {}, {}, []
    for entry in sorted(os.listdir(source_dir)):
        folder = os.path.join(source_dir, entry)
        if not os.path.isdir(folder):
            continue
        if os.path.exists(os.path.join(folder, "pack.json")):
            add_pack(rb, folder, entry, listings, assets, releases, warnings)
        elif os.path.exists(os.path.join(folder, "widget.json")):
            add_listing(rb, folder, entry, listings, assets, warnings)
    index = {
        "listings": [listings[wid] for wid in sorted(listings)],
        "assets": [assets[wid] for wid in sorted(assets)],
        "releases": [releases[name] for name in sorted(releases)],
    }
    return index, warnings


def main(argv):
    if len(argv) != 4 or argv[1] != "build":
        print("error: usage: ifthe-index.py build SOURCE_DIR OUT_FILE",
              file=sys.stderr)
        return 1
    try:
        index, warnings = build(argv[2])
    except IndexError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for line in warnings:
        print(f"warning: {line}", file=sys.stderr)
    try:
        with open(argv[3], "w") as fh:
            json.dump(index, fh, indent=2)
            fh.write("\n")
    except OSError as exc:
        print(f"error: cannot write {argv[3]}: {exc.strerror or exc}",
              file=sys.stderr)
        return 1
    print(f"index: {len(index['listings'])} listings, "
          f"{len(index['assets'])} assets, "
          f"{len(index['releases'])} releases")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
