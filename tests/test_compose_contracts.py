#!/usr/bin/env python3
"""Cross-file consistency tests for the ifthe deploy config contracts.

Checks (all runnable here, no Docker):
  1. Every ${VAR} referenced in a compose file (without a :- default) is defined in .env.example.
  2. Host ports are unique across all four compose files.
  3. Every ${DATA_ROOT}/<path> bind mount is created by 00-create-dirs.sh.
Exits non-zero if any hard inconsistency is found.
"""
import re, sys, glob
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEPLOY = REPO / "apps" / "deploy"
COMPOSE = sorted(glob.glob(str(DEPLOY / "docker-compose.*.yml")))
ENV = (DEPLOY / ".env.example").read_text()
CREATE = (DEPLOY / "00-create-dirs.sh").read_text()

findings = []
def fail(msg): findings.append(msg)

# always-present / externally-provided vars that need not appear in .env.example
INTRINSIC = {"DATA_ROOT", "TZ", "PUID", "PGID"}
env_keys = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", ENV, re.M))

# ---- 1. env-var references ----
ref_re = re.compile(r"\$\{([A-Z][A-Z0-9_]+)(:-[^}]*)?\}")
referenced = {}
for f in COMPOSE:
    txt = Path(f).read_text()
    for m in ref_re.finditer(txt):
        var, has_default = m.group(1), bool(m.group(2))
        referenced.setdefault(var, has_default)
        # if any reference has no default, treat as required
        if not has_default:
            referenced[var] = False
for var, has_default in sorted(referenced.items()):
    if var in INTRINSIC:
        continue
    if var not in env_keys and not has_default:
        fail(f"[env] ${{{var}}} referenced in compose but not defined in .env.example (and no :- default)")

# ---- 2. host port uniqueness ----
# match "127.0.0.1:8222:80", "8000:8000", "53:53/tcp" -> host port is the field before the last ':container'
port_line = re.compile(r'^\s*-\s*"?(?:(\d+\.\d+\.\d+\.\d+):)?(\d+):(\d+)(?:/(tcp|udp))?"?\s*$')
host_ports = {}
for f in COMPOSE:
    in_ports = False
    for ln in Path(f).read_text().splitlines():
        if re.match(r'^\s*ports:\s*$', ln):
            in_ports = True; continue
        if in_ports:
            m = port_line.match(ln)
            if m:
                proto = m.group(4) or "tcp"
                key = f"{m.group(2)}/{proto}"
                if key in host_ports:
                    fail(f"[ports] host port {key} mapped twice: {host_ports[key]} and {Path(f).name}")
                host_ports[key] = Path(f).name
            elif not re.match(r'^\s*-', ln) and ln.strip() and not ln.strip().startswith("#"):
                in_ports = False

# ---- 3. DATA_ROOT bind-mount paths are created ----
# created dirs from the dirs=( ... ) array
mcreate = re.search(r"dirs=\((.*?)\)", CREATE, re.S)
created = set()
if mcreate:
    for tok in mcreate.group(1).split():
        tok = tok.strip().strip('"').strip("'")
        if tok:
            created.add(tok)
            created.add(tok.split("/")[0])  # parent counts as created (mkdir -p)
# expand: a mount under created 'paperless/consume' is covered by created entry 'paperless/consume'
def is_created(sub):
    sub = sub.strip("/")
    if sub in created:
        return True
    # mkdir -p of a deeper path covers parents; and a created deeper path covers itself
    return any(c == sub or c.startswith(sub + "/") or sub.startswith(c + "/") for c in created)

mount_re = re.compile(r'\$\{DATA_ROOT\}/([^:"\s]+):')
for f in COMPOSE:
    for sub in set(mount_re.findall(Path(f).read_text())):
        if not is_created(sub):
            fail(f"[mounts] {Path(f).name}: bind mount ${{DATA_ROOT}}/{sub} has no matching dir in 00-create-dirs.sh")

# ---- 4. health gating, restart policy, and log bounds (quality loop) ----
# The emulator findings encoded in the compose files: the five gating
# healthchecks carry start_period 60s, dependents wait for service_healthy,
# every service restarts unless-stopped, and logs are bounded per stack.
texts = {Path(f).name: Path(f).read_text() for f in COMPOSE}
sp_total = sum(t.count("start_period: 60s") for t in texts.values())
if sp_total != 5:
    fail(f"[gating] expected 5 healthchecks with start_period: 60s, found {sp_total}")
for fname, want in (("docker-compose.docs.yml", 3), ("docker-compose.family.yml", 4)):
    got = texts[fname].count("condition: service_healthy")
    if got != want:
        fail(f"[gating] {fname}: expected {want} service_healthy conditions, found {got}")
for name in ("paperless-redis", "paperless-db", "paperless-gotenberg",
             "nextcloud-db", "nextcloud-redis"):
    if not any(name + ":" in t for t in texts.values()):
        fail(f"[gating] gating service {name} not found in any compose file")
for fname, t in texts.items():
    if "restart: unless-stopped" not in t:
        fail(f"[restart] {fname}: no service uses restart: unless-stopped")
    for bad in ("restart: always", 'restart: "no"', "restart: on-failure"):
        if bad in t:
            fail(f"[restart] {fname}: unexpected restart policy {bad}")
    if 'max-size: "10m"' not in t or 'max-file: "3"' not in t:
        fail(f"[logging] {fname}: json-file log bounds (10m x 3) missing")

# ---- report ----
print(f"compose-contracts: {len(COMPOSE)} files, {len(host_ports)} host ports, {len(created)} created dirs")
print("host ports:", ", ".join(sorted(host_ports)))
if findings:
    print(f"\n{len(findings)} FINDING(S):")
    for x in findings:
        print("  FAIL " + x)
    sys.exit(1)
print("PASS: env refs resolved, ports unique, bind mounts all created")
sys.exit(0)
