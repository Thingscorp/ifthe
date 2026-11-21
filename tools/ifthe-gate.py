#!/usr/bin/env python3
"""Check one widget folder against the ifthe contribution gate.

The gate runs the same checks the briefing renderer's loader runs,
in the renderer's order, and nothing else:

  - the folder holds no code file (the data-only rule, checked with
    the renderer's own folder_code_file: a code suffix, an executable
    bit, or a shebang line refuses the folder whole);
  - widget.json is present, readable, under the renderer's 64 KB
    budget, and passes the renderer's own validate_manifest (required
    fields, id shape and folder match, slot, profiles, template,
    reads, and the settings declarations);
  - data.json, when present, is readable and under the same budget.

That is the whole listing minimum: a present, valid widget.json.
No category, no author, no extra field is demanded.

The answer is one line, in the portal's end states:

  LIVE: <widget id>          every check passed (exit 0)
  REFUSED: <one named reason>  the first failed check (exit 1)

Standard library only, no network, no state. validate_manifest is
imported from briefing/render_briefing.py, never copied.

  python3 tools/ifthe-gate.py check WIDGET_DIR
"""
import importlib.util, os, sys


def load_renderer():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "briefing", "render_briefing.py")
    spec = importlib.util.spec_from_file_location("render_briefing", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(widget_dir):
    """Return (manifest, refusal reason); exactly one of them is None."""
    rb = load_renderer()
    folder_name = os.path.basename(os.path.normpath(widget_dir))
    if not os.path.isdir(widget_dir):
        return None, f"no folder {widget_dir}"
    code = rb.folder_code_file(widget_dir)
    if code is not None:
        return None, f"folder holds code file {code}"
    manifest_path = os.path.join(widget_dir, "widget.json")
    if not os.path.exists(manifest_path):
        return None, "no widget.json"
    manifest, error = rb.read_widget_file(manifest_path, folder_name,
                                          "widget.json")
    if error is not None:
        return None, error
    error = rb.validate_manifest(manifest, folder_name)
    if error is not None:
        return None, error
    data_path = os.path.join(widget_dir, "data.json")
    if os.path.exists(data_path):
        _data, error = rb.read_widget_file(data_path, manifest["id"],
                                           "data.json")
        if error is not None:
            return None, error
    return manifest, None


def main(argv):
    if len(argv) != 3 or argv[1] != "check":
        print("error: usage: ifthe-gate.py check WIDGET_DIR", file=sys.stderr)
        return 1
    manifest, reason = check(argv[2])
    if reason is not None:
        print(f"REFUSED: {reason}")
        return 1
    print(f"LIVE: {manifest['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
