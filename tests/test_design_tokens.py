#!/usr/bin/env python3
"""Design token drift guard: DESIGN.md frontmatter against the code surfaces.

Iteration 6 of the Ralph loop completed the DESIGN.md type ramp and showed
that most detector noise was an incomplete token record, not wrong code.
This test holds that record: when a token in DESIGN.md stops matching the
code it documents, the suite fails and names the token.

Checks:
  1. Every color in the DESIGN.md frontmatter appears in at least one of
     the code surfaces the source map assigns to it. Hexes are compared
     normalized, so the shorthand forms the code uses (#333, #eee, #fff)
     and alpha forms (#5c665040) count as their base color.
  2. Every fontSize in the frontmatter typography ramp appears as a
     font-size value in its mapped surface. Sizes are compared with
     whitespace removed and leading zeros dropped, so the code forms
     (clamp(22px,4vw,30px), .85rem) match the documented forms.
  3. The brand accent agrees in three places: DESIGN.md colors.primary,
     site/brand.yml colors.accent, and the landing CSS in site/index.html.

Source map discipline: every token in DESIGN.md must be listed in a map
below or in a DOC_ONLY dict with a one-line reason. An unmapped token
fails the suite, and a map entry for a token DESIGN.md no longer has
fails too, so the map itself cannot rot silently. apps.json is not a
surface here: it holds per-app icon colors only, and no DESIGN.md token
lives there today.
"""
import re, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "DESIGN.md"
BRAND = REPO / "site" / "brand.yml"

SURFACES = {
    "landing": REPO / "site" / "index.html",
    "briefing": REPO / "briefing" / "render_briefing.py",
    "frontdoor": REPO / "apps" / "dashboard" / "frontdoor" / "styles.css",
}

# Token name -> surfaces where that token is allowed to be found.
COLOR_HOME = {
    "primary": ["landing", "briefing", "frontdoor"],
    "primary-deep": ["landing"],
    "ink": ["landing", "briefing"],
    "ink-frontdoor": ["frontdoor"],
    "paper": ["briefing"],
    "neutral-bg": ["landing", "briefing", "frontdoor"],
    "frontdoor-bg": ["frontdoor"],
    "body": ["landing"],
    "secondary": ["landing", "briefing"],
    "muted": ["landing"],
    "faint": ["landing"],
    "hairline": ["landing"],
    "briefing-label": ["briefing"],
    "briefing-muted": ["briefing"],
    "briefing-rule": ["briefing"],
    "pure-black": ["briefing"],
    "ok": ["briefing"],
    "warn": ["briefing"],
    "dark-bg": ["frontdoor"],
    "dark-surface": ["frontdoor"],
    "dark-text": ["frontdoor"],
    "dark-muted": ["frontdoor"],
    "dark-accent": ["frontdoor"],
}

# Token name -> reason it has no code surface. Empty today: every color
# in DESIGN.md is live in code. A future doc-only token goes here with
# its reason, never as a silent skip in COLOR_HOME.
DOC_ONLY_COLORS = {}

TYPE_HOME = {
    "display": ["landing"],
    "headline": ["frontdoor"],
    "title": ["landing"],
    "body": ["landing"],
    "label": ["briefing"],
    "caption": ["landing"],
    "display-mobile": ["landing"],
    "body-mobile": ["landing"],
    "ambient-clock": ["frontdoor"],
    "ambient-date": ["frontdoor"],
    "ambient-agenda": ["frontdoor"],
    "app-icon": ["frontdoor"],
    "app-desc": ["frontdoor"],
    "frontdoor-note": ["frontdoor"],
}

# Same rule as DOC_ONLY_COLORS. Empty today.
DOC_ONLY_TYPE = {}

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def norm_hex(value):
    """Normalize a hex color to #rrggbb lowercase.

    Expands shorthand (#333 -> #333333) and drops the alpha channel of
    8-digit forms (#5c665040 -> #5c6650), because both spellings in code
    are the same base token.
    """
    h = str(value).strip().lower().lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    if len(h) == 8:
        h = h[:6]
    return "#" + h


def norm_size(value):
    """Normalize a font-size for comparison: no whitespace, no leading 0."""
    v = re.sub(r"\s+", "", str(value).strip().lower())
    return re.sub(r"(?<![0-9])0\.", ".", v)


def surface_hexes(text):
    found = set()
    for raw in re.findall(r"#[0-9a-fA-F]+", text):
        if len(raw) - 1 in (3, 4, 6, 8):
            found.add(norm_hex(raw))
    return found


def surface_sizes(text):
    return {norm_size(v) for v in re.findall(r"font-size\s*:\s*([^;}]+)", text)}


def frontmatter(path):
    text = path.read_text()
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        raise SystemExit(f"no YAML frontmatter found in {path}")
    body = parts[1]
    # Tolerate HTML comment lines (tooling schema markers) around the YAML.
    body = "\n".join(
        line for line in body.splitlines()
        if not line.strip().startswith("<!--")
    )
    return yaml.safe_load(body)


design = frontmatter(DESIGN)
brand = yaml.safe_load(BRAND.read_text())
texts = {name: path.read_text() for name, path in SURFACES.items()}
hexes = {name: surface_hexes(t) for name, t in texts.items()}
sizes = {name: surface_sizes(t) for name, t in texts.items()}

colors = design.get("colors") or {}
typography = design.get("typography") or {}

# ---- map completeness, both directions ----
check("every DESIGN.md color is mapped or doc-only",
      set(colors) == set(COLOR_HOME) | set(DOC_ONLY_COLORS),
      "unmapped: %s; stale map entries: %s" % (
          sorted(set(colors) - set(COLOR_HOME) - set(DOC_ONLY_COLORS)),
          sorted((set(COLOR_HOME) | set(DOC_ONLY_COLORS)) - set(colors))))
check("every DESIGN.md type role is mapped or doc-only",
      set(typography) == set(TYPE_HOME) | set(DOC_ONLY_TYPE),
      "unmapped: %s; stale map entries: %s" % (
          sorted(set(typography) - set(TYPE_HOME) - set(DOC_ONLY_TYPE)),
          sorted((set(TYPE_HOME) | set(DOC_ONLY_TYPE)) - set(typography))))

# ---- colors: each token present in at least one mapped surface ----
for name in sorted(colors):
    if name in DOC_ONLY_COLORS:
        check(f"color '{name}' is doc-only ({DOC_ONLY_COLORS[name]})", True)
        continue
    want = norm_hex(colors[name])
    homes = COLOR_HOME[name]
    found_in = [s for s in homes if want in hexes[s]]
    check(f"color '{name}' ({want}) present in code",
          bool(found_in),
          f"expected in one of {homes}, found in none")

# ---- typography: each fontSize present in at least one mapped surface ----
for role in sorted(typography):
    if role in DOC_ONLY_TYPE:
        check(f"type role '{role}' is doc-only ({DOC_ONLY_TYPE[role]})", True)
        continue
    want = norm_size(typography[role].get("fontSize", ""))
    homes = TYPE_HOME[role]
    found_in = [s for s in homes if want in sizes[s]]
    check(f"type role '{role}' fontSize ({typography[role].get('fontSize')}) present in code",
          bool(found_in),
          f"expected in one of {homes}, found in none")

# ---- the accent agrees in three places ----
design_accent = norm_hex(colors.get("primary", ""))
brand_accent = norm_hex((brand.get("colors") or {}).get("accent", ""))
check("accent: DESIGN.md primary equals brand.yml accent",
      design_accent == brand_accent,
      f"DESIGN.md {design_accent} vs brand.yml {brand_accent}")
check("accent: landing CSS uses the agreed accent",
      design_accent in hexes["landing"],
      f"{design_accent} not found in site/index.html")

passed = sum(1 for _, ok, _ in results if ok)
fails = [(n, d) for n, ok, d in results if not ok]
print(f"\ndesign_tokens: {passed}/{len(results)} checks passed")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}"
          + (f"   [{d}]" if (not ok and d) else ""))
sys.exit(1 if fails else 0)
