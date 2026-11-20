#!/usr/bin/env python3
"""Cross-file consistency tests for the ifthe DASHBOARD contracts.

Ties the dashboard surfaces back to the published host ports so a service can't
appear on the launcher / health monitor at a port that nothing actually exposes.

Checks (all runnable here, no Docker):
  1. Every port linked from dashboard/glance.yml monitor sites resolves to a
     published host port (front door 8086 + glance 8085 included).
  2. dashboard/frontdoor/apps.json is valid JSON; every entry has name + url,
     each url carries a scheme + the {host} placeholder, and any :PORT in a url
     is a published host port.
  3. glance.yml has the expected pages -> columns -> widgets structure.

The published-host-port set is collected from the compose `ports:` blocks, plus
Actual Budget's :5006 — Actual runs on the host *outside* these compose files
(see deploy/README.md) and its port is taken from the ACTUAL_SERVER_URL default
in docker-compose.ai.yml so it stays grounded in the real tree.

The Vaultwarden entries are tailnet-only HTTPS (no LAN :port) and are skipped.
Exits non-zero if any hard inconsistency is found.
"""
import re, sys, json, glob
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
APPS = REPO / "apps"
DEPLOY = APPS / "deploy"
DASH = APPS / "dashboard"
COMPOSE = sorted(glob.glob(str(DEPLOY / "docker-compose.*.yml")))
GLANCE = DASH / "glance.yml"
APPS_JSON = DASH / "frontdoor" / "apps.json"

findings = []
def fail(msg): findings.append(msg)

# ---- collect published HOST ports from every compose ports: block ----
# match "127.0.0.1:8222:80", "8000:8000", "53:53/tcp" -> host port is group(2)
# (tolerate a trailing inline comment, e.g.  - "8083:80/tcp"  # admin web UI)
port_line = re.compile(r'^\s*-\s*"?(?:(\d+\.\d+\.\d+\.\d+):)?(\d+):(\d+)(?:/(tcp|udp))?"?\s*(?:#.*)?$')
host_ports = set()
for f in COMPOSE:
    in_ports = False
    for ln in Path(f).read_text().splitlines():
        if re.match(r'^\s*ports:\s*$', ln):
            in_ports = True; continue
        if in_ports:
            m = port_line.match(ln)
            if m:
                host_ports.add(m.group(2))
            elif not re.match(r'^\s*-', ln) and ln.strip() and not ln.strip().startswith("#"):
                in_ports = False

# Actual Budget runs on the host outside these compose files; its LAN port comes
# from the ACTUAL_SERVER_URL default in the AI compose (kept grounded, not hardcoded).
ai_txt = (DEPLOY / "docker-compose.ai.yml").read_text()
for p in re.findall(r"ACTUAL_SERVER_URL[^\n]*?:(\d+)", ai_txt):
    host_ports.add(p)

# ---- load the dashboard configs ----
glance = yaml.safe_load(GLANCE.read_text())
apps = json.loads(APPS_JSON.read_text())

# ---- 1. glance monitor site ports resolve to published host ports ----
url_port = re.compile(r"https?://[^/\s]*?:(\d+)")
monitor_sites = []
for page in (glance.get("pages") or []):
    for col in (page.get("columns") or []):
        for w in (col.get("widgets") or []):
            if w.get("type") == "monitor":
                monitor_sites.extend(w.get("sites") or [])

if not monitor_sites:
    fail("[glance] no monitor sites found to check")

for site in monitor_sites:
    url = site.get("url", "")
    m = url_port.match(url)
    if not m:
        # https URL with no :port (e.g. Vaultwarden tailnet) -> no LAN port, skip
        continue
    port = m.group(1)
    if port not in host_ports:
        fail(f"[glance] monitor '{site.get('title')}' -> :{port} is not a published host port")

# the dashboard's own surfaces must be reachable: front door 8086 + glance 8085
for required in ("8086", "8085"):
    if required not in host_ports:
        fail(f"[glance] dashboard port :{required} is not a published host port")

# ---- 2. apps.json: valid JSON, name+url, scheme + {host}, ports published ----
if not isinstance(apps, list) or not apps:
    fail("[apps] apps.json must be a non-empty JSON array")

scheme_re = re.compile(r"^https?://")
for i, entry in enumerate(apps if isinstance(apps, list) else []):
    if not isinstance(entry, dict):
        fail(f"[apps] entry #{i} is not an object"); continue
    name = entry.get("name")
    url = entry.get("url")
    if not name:
        fail(f"[apps] entry #{i} missing 'name'")
    if not url:
        fail(f"[apps] entry {name!r} missing 'url'"); continue
    if not scheme_re.match(url):
        fail(f"[apps] entry {name!r} url {url!r} has no http(s) scheme")
    if "{host}" not in url:
        fail(f"[apps] entry {name!r} url {url!r} missing {{host}} placeholder")
    m = url_port.match(url)
    if not m:
        # e.g. Vaultwarden https://{host} with no port -> tailnet only, skip
        continue
    port = m.group(1)
    if port not in host_ports:
        fail(f"[apps] entry {name!r} -> :{port} is not a published host port")

# ---- 3. glance.yml structure: pages -> columns -> widgets ----
pages = glance.get("pages")
if not isinstance(pages, list) or not pages:
    fail("[structure] glance.yml has no 'pages' list")
else:
    for pi, page in enumerate(pages):
        cols = page.get("columns") if isinstance(page, dict) else None
        if not isinstance(cols, list) or not cols:
            fail(f"[structure] page #{pi} has no 'columns' list"); continue
        for ci, col in enumerate(cols):
            widgets = col.get("widgets") if isinstance(col, dict) else None
            if not isinstance(widgets, list) or not widgets:
                fail(f"[structure] page #{pi} column #{ci} has no 'widgets' list")

# ---- report ----
print(f"dashboard-contracts: {len(host_ports)} host ports, "
      f"{len(monitor_sites)} monitor sites, {len(apps) if isinstance(apps, list) else 0} app entries")
print("host ports:", ", ".join(sorted(host_ports, key=int)))
if findings:
    print(f"\n{len(findings)} FINDING(S):")
    for x in findings:
        print("  FAIL " + x)
    sys.exit(1)
print("PASS — dashboard ports resolve, apps.json well-formed, glance structure intact")
sys.exit(0)
