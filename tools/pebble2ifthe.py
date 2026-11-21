#!/usr/bin/env python3
"""Convert a Pebble app's Clay configuration into an ifthe widget folder.

Reads an input folder holding:

  package.json   a Pebble-style manifest. Its "pebble" key carries
                 "displayName" and "messageKeys": every key the app
                 declares. Only declared keys can carry a value, exactly
                 as on Pebble.
  config.json    the Clay config: one JSON array of typed items
                 (clay.json or clay-config.json are also accepted).

Writes an output folder holding one widget folder, named for the
generated widget id:

  <output>/<widget-id>/widget.json   the ifthe manifest
  <output>/<widget-id>/data.json     starting values for the declared keys

Data only: the script writes nothing else, uses no network, keeps no
state. Standard library only.

  python3 tools/pebble2ifthe.py INPUT_DIR OUTPUT_DIR

Mapping, confirmed against briefing/render_briefing.py: the renderer's
validate_settings accepts only the setting types "toggle", "select"
and "input", and its SETTING_KEY_RE accepts only lowercase snake_case
keys. So:

  Clay toggle     -> ifthe toggle
  Clay input      -> ifthe input
  Clay select     -> ifthe select (option values become the options)
  Clay radiogroup -> ifthe select (one choice from a list)
  Clay slider, color, checkboxgroup, and any custom type are dropped:
  the renderer has no setting type that honours them. A dropped item
  whose key is declared still leaves its Clay default in data.json.

Layout-only Clay types (section, heading, text) and form types
(button, submit) are dropped. Sections are opened and their items are
converted. A Clay item whose messageKey is not declared in the
manifest is dropped, exactly as Pebble drops undeclared values. Every
drop is reported on stdout by name, with the reason. The last line of
stdout is the summary: widget id, settings count, dropped count.
"""
import hashlib, json, os, re, sys

CLAY_CONFIG_NAMES = ("config.json", "clay.json", "clay-config.json")
LAYOUT_TYPES = ("section", "heading", "text")
FORM_TYPES = ("button", "submit")
VERSION_RE = re.compile(r"^\d+(?:\.\d+)*$")
ARRAY_KEY_RE = re.compile(r"^(.+?)(?:\[(\d*)\])?$")


class ConvertError(Exception):
    pass


def load_json(path, label):
    try:
        with open(path) as fh:
            return json.load(fh)
    except OSError as exc:
        raise ConvertError(f"cannot read {label}: {exc.strerror or exc}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConvertError(f"bad {label}: {exc}")


def base_key(raw):
    """The message key without its array suffix: 'food[3]' -> 'food'."""
    match = ARRAY_KEY_RE.match(raw.strip())
    return match.group(1) if match else raw.strip()


def setting_key(raw):
    """Normalize a Pebble message key to the renderer's key shape.

    The renderer accepts only ^[a-z][a-z0-9_]*$ (SETTING_KEY_RE in
    render_briefing.py). Pebble keys are often camelCase, so case
    boundaries and dashes become underscores and the rest is lowered.
    """
    key = base_key(raw).replace("-", "_")
    key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    key = re.sub(r"[^a-zA-Z0-9_]", "_", key).lower()
    key = re.sub(r"_+", "_", key).strip("_")
    if not key:
        return ""
    if not key[0].isalpha():
        key = "key_" + key
    return key


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "widget"


def widget_id(package):
    name = package.get("name")
    if not isinstance(name, str) or not name.strip():
        name = "pebble-widget"
    base = name.strip()
    if base.startswith("@") and "/" in base:
        base = base.split("/", 1)[1]
    display = package.get("pebble", {}).get("displayName")
    seed = f"{name}|{display if isinstance(display, str) else ''}"
    suffix = hashlib.sha256(seed.encode()).hexdigest()[:6]
    return f"{slugify(base)}-{suffix}"


def normalize_version(raw):
    if isinstance(raw, str) and VERSION_RE.match(raw.strip()):
        parts = (raw.strip().split(".") + ["0", "0", "0"])[:3]
        return ".".join(parts)
    return "1.0.0"


def declared_keys(package):
    """Ordered (raw key, setting key) pairs from pebble.messageKeys.

    messageKeys may be a list of key names (with optional [n] array
    suffixes) or an object keyed by name, the two shapes Pebble tools
    have used. Duplicates after normalization keep the first.
    """
    pebble = package.get("pebble")
    if not isinstance(pebble, dict):
        raise ConvertError("package.json has no pebble object")
    raw_keys = pebble.get("messageKeys")
    if isinstance(raw_keys, dict):
        names = list(raw_keys)
    elif isinstance(raw_keys, list):
        names = [k for k in raw_keys if isinstance(k, str)]
    else:
        raise ConvertError("pebble.messageKeys must be a list or an object")
    pairs, seen = [], set()
    for name in names:
        skey = setting_key(name)
        if skey and skey not in seen:
            seen.add(skey)
            pairs.append((base_key(name), skey))
    if not pairs:
        raise ConvertError("pebble.messageKeys declares no keys")
    return pairs


def flatten_items(items):
    """Yield Clay items in page order, opening sections as met."""
    for item in items:
        if isinstance(item, dict) and item.get("type") == "section":
            yield item
            children = item.get("items")
            if isinstance(children, list):
                yield from flatten_items(children)
        else:
            yield item


def item_name(item):
    for field in ("messageKey", "id"):
        value = item.get(field)
        if isinstance(value, str) and value:
            return value
    value = item.get("defaultValue")
    if isinstance(value, str) and value:
        return value[:24]
    return str(item.get("type"))


def item_label(item, skey):
    label = item.get("label")
    if isinstance(label, str) and label:
        return label
    return skey.replace("_", " ")


def option_values(item):
    """Flatten a Clay options list to plain value strings.

    Options are {label, value} objects, plain strings, or optgroups
    whose value is itself a list of options.
    """
    values = []

    def walk(options):
        for option in options:
            if isinstance(option, dict):
                value = option.get("value")
                if isinstance(value, list):
                    walk(value)
                elif value is not None:
                    values.append(str(value))
            elif isinstance(option, (str, int, float)) \
                    and not isinstance(option, bool):
                values.append(str(option))

    options = item.get("options")
    if isinstance(options, list):
        walk(options)
    return values


def toggle_default(item):
    value = item.get("defaultValue")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    return False


def convert_item(item, skey):
    """Build one ifthe setting declaration from a mappable Clay item.

    Returns (declaration, data value). Raises ValueError with the
    reason when the renderer cannot honour the item.
    """
    kind = item.get("type")
    label = item_label(item, skey)
    if kind == "toggle":
        default = toggle_default(item)
        return {"key": skey, "type": "toggle", "label": label,
                "default": default}, default
    if kind == "input":
        raw = item.get("defaultValue")
        default = raw if isinstance(raw, str) else (
            str(raw) if isinstance(raw, (int, float))
            and not isinstance(raw, bool) else "")
        return {"key": skey, "type": "input", "label": label,
                "default": default}, default
    if kind in ("select", "radiogroup"):
        options = option_values(item)
        if not options:
            raise ValueError(f"{kind} has no usable options")
        declaration = {"key": skey, "type": "select", "label": label,
                       "options": options}
        raw = item.get("defaultValue")
        default = str(raw) if raw is not None and str(raw) in options else None
        if default is not None:
            declaration["default"] = default
        return declaration, default
    raise ValueError(
        f"the renderer has no setting type for Clay type {kind}")


def dropped_default(item):
    """The data.json starting value for a declared key whose Clay item
    was dropped as unmappable: its Clay default, or an empty shape."""
    if "defaultValue" in item:
        return item["defaultValue"]
    if item.get("type") == "checkboxgroup":
        options = item.get("options")
        return [False] * len(options) if isinstance(options, list) else []
    return None


def convert(input_dir):
    package_path = os.path.join(input_dir, "package.json")
    if not os.path.exists(package_path):
        raise ConvertError(f"no package.json in {input_dir}")
    package = load_json(package_path, "package.json")
    if not isinstance(package, dict):
        raise ConvertError("package.json must hold an object")
    pairs = declared_keys(package)
    declared = {skey for _, skey in pairs}

    clay_path = None
    for name in CLAY_CONFIG_NAMES:
        candidate = os.path.join(input_dir, name)
        if os.path.exists(candidate):
            clay_path = candidate
            break
    if clay_path is None:
        raise ConvertError(
            f"no Clay config ({CLAY_CONFIG_NAMES[0]}) in {input_dir}")
    clay = load_json(clay_path, "Clay config")
    if not isinstance(clay, list):
        raise ConvertError("the Clay config must be a JSON array")

    settings = []
    values = {}
    claimed = set()
    dropped = []

    def drop(item, reason):
        dropped.append(
            f"dropped: {item_name(item)} ({item.get('type')}): {reason}")

    for item in flatten_items(clay):
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            dropped.append("dropped: an item with no type: not a Clay item")
            continue
        kind = item["type"]
        if kind == "section":
            drop(item, "layout only, its items are converted in place")
            continue
        if kind in LAYOUT_TYPES:
            drop(item, "layout only, the briefing has no such element")
            continue
        if kind in FORM_TYPES:
            drop(item, "a form control, the briefing has no forms")
            continue
        raw_key = item.get("messageKey")
        if not isinstance(raw_key, str) or not raw_key:
            drop(item, "no messageKey, its value could not persist on Pebble")
            continue
        skey = setting_key(raw_key)
        if skey not in declared:
            drop(item, f"messageKey {raw_key} is not declared in package.json")
            continue
        if skey in claimed:
            drop(item, f"key {skey} already converted from an earlier item")
            continue
        claimed.add(skey)
        try:
            declaration, value = convert_item(item, skey)
        except ValueError as exc:
            drop(item, str(exc))
            values[skey] = dropped_default(item)
            continue
        settings.append(declaration)
        values[skey] = value

    data = {skey: values.get(skey) for _, skey in pairs}

    pebble = package["pebble"]
    title = pebble.get("displayName")
    if not isinstance(title, str) or not title:
        title = package.get("name") if isinstance(package.get("name"), str) \
            else "Converted widget"
    manifest = {
        "id": widget_id(package),
        "title": title,
        "version": normalize_version(package.get("version")),
        "slot": "main",
        "order": 50,
        "profiles": ["panel", "card", "kindle"],
        "template": "text",
        "reads": [],
        "settings": settings,
    }
    author = package.get("author")
    if isinstance(author, dict):
        author = author.get("name")
    if isinstance(author, str) and author:
        manifest["author"] = author
    return manifest, data, dropped


def main(argv):
    if len(argv) != 3:
        print("error: usage: pebble2ifthe.py INPUT_DIR OUTPUT_DIR",
              file=sys.stderr)
        return 1
    input_dir, output_dir = argv[1], argv[2]
    try:
        manifest, data, dropped = convert(input_dir)
    except ConvertError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    widget_dir = os.path.join(output_dir, manifest["id"])
    os.makedirs(widget_dir, exist_ok=True)
    with open(os.path.join(widget_dir, "widget.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    with open(os.path.join(widget_dir, "data.json"), "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    for line in dropped:
        print(line)
    print(f"widget {manifest['id']}: {len(manifest['settings'])} settings, "
          f"{len(dropped)} dropped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
