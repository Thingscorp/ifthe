#!/usr/bin/env python3
"""Install an ifthe widget pack into a widgets root.

A pack is a folder of widget folders plus one pack.json at its root
(the format fixed in briefing/WIDGETS.md, "Packs"):

  pack.json   { "name": "@russ/morning-pack", "version": "1.0.0",
                "widgets": ["land-hunt", "house-plants"] }

Install copies the pack's widget folders into a widgets root, where
the briefing renderer's normal discovery finds them:

  python3 tools/ifthe-pack.py install PACK_DIR WIDGETS_ROOT

Every check runs before anything is copied, so a pack that fails a
check installs nothing. The checks, in order:

  - pack.json is present, holds an object, and its name is a scoped
    name (@handle/slug), its version is major.minor.patch, and its
    widgets field is a list of widget ids.
  - every listed widget has a folder in the pack, and that folder's
    widget.json parses (under the renderer's 64 KB budget) with an id
    that matches the folder name and a major.minor.patch version.
  - a widget already in the root is replaced only when the incoming
    version is higher; an equal or lower version refuses the whole
    install and names the widget.

Data only: the tool copies folders and keeps no state. Standard
library only. The last line of stdout is the summary: pack name,
version, widget count.
"""
import importlib.util, json, os, re, shutil, sys

PACK_NAME_RE = re.compile(r"^@[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*$")


class PackError(Exception):
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
        raise PackError(f"cannot read {label}: {exc.strerror or exc}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackError(f"bad {label}: {exc}")


def version_key(version):
    return tuple(int(part) for part in version.split("."))


def read_pack(pack_dir):
    if not os.path.isdir(pack_dir):
        raise PackError(f"no pack folder {pack_dir}")
    pack_path = os.path.join(pack_dir, "pack.json")
    if not os.path.exists(pack_path):
        raise PackError("pack has no pack.json")
    pack = load_json(pack_path, "pack.json")
    if not isinstance(pack, dict):
        raise PackError("pack.json must hold an object")
    name = pack.get("name")
    if not isinstance(name, str) or not PACK_NAME_RE.match(name):
        raise PackError("pack name must be a scoped name like @russ/morning-pack")
    return pack


def check_pack(rb, pack_dir, pack, widgets_root):
    """Run every install check. Return [(widget id, source, target)]."""
    version = pack.get("version")
    if not isinstance(version, str) or not rb.VERSION_RE.match(version):
        raise PackError("pack version must be major.minor.patch")
    widgets = pack.get("widgets")
    if not isinstance(widgets, list) \
            or any(not isinstance(w, str) for w in widgets):
        raise PackError("pack widgets must be a list of widget ids")
    plan = []
    for wid in widgets:
        folder = os.path.join(pack_dir, wid)
        if not os.path.isdir(folder):
            raise PackError(f"widget {wid}: no folder in the pack")
        manifest_path = os.path.join(folder, "widget.json")
        if not os.path.exists(manifest_path):
            raise PackError(f"widget {wid}: no widget.json")
        manifest, error = rb.read_widget_file(manifest_path, wid, "widget.json")
        if error is not None:
            raise PackError(f"widget {wid}: {error}")
        if not isinstance(manifest, dict) or manifest.get("id") != wid:
            raise PackError(
                f"widget {wid}: widget.json id does not match the folder name")
        incoming = manifest.get("version")
        if not isinstance(incoming, str) or not rb.VERSION_RE.match(incoming):
            raise PackError(f"widget {wid}: version must be major.minor.patch")
        target = os.path.join(widgets_root, wid)
        if os.path.isdir(target):
            installed_path = os.path.join(target, "widget.json")
            if not os.path.exists(installed_path):
                raise PackError(
                    f"widget {wid}: installed copy has no widget.json")
            installed, error = rb.read_widget_file(
                installed_path, wid, "widget.json")
            if error is not None:
                raise PackError(f"widget {wid}: installed copy: {error}")
            current = installed.get("version") if isinstance(installed, dict) \
                else None
            if not isinstance(current, str) or not rb.VERSION_RE.match(current):
                raise PackError(
                    f"widget {wid}: installed copy has no readable version")
            if version_key(incoming) <= version_key(current):
                raise PackError(
                    f"widget {wid}: incoming version {incoming} is not "
                    f"higher than installed {current}")
        plan.append((wid, folder, target))
    return plan


def install(pack_dir, widgets_root):
    rb = load_renderer()
    pack = read_pack(pack_dir)
    plan = check_pack(rb, pack_dir, pack, widgets_root)
    os.makedirs(widgets_root, exist_ok=True)
    for _wid, folder, target in plan:
        if os.path.isdir(target):
            shutil.rmtree(target)
        shutil.copytree(folder, target)
    return f"pack {pack['name']} {pack['version']}: {len(plan)} widgets installed"


def main(argv):
    if len(argv) != 4 or argv[1] != "install":
        print("error: usage: ifthe-pack.py install PACK_DIR WIDGETS_ROOT",
              file=sys.stderr)
        return 1
    try:
        summary = install(argv[2], argv[3])
    except PackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
