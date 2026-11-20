#!/usr/bin/env bash
# ============================================================
# ifthe :: verification gates
# ------------------------------------------------------------
# Exit 0 only if EVERY check passes. This is the project's gate
# and a good pre-commit check.
#   bash scripts/check.sh
# ============================================================
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1
cd "$(cd "$(dirname "$0")/.." && pwd)"
rc=0
step(){ printf '\n=== %s ===\n' "$1"; }

step "read-only money guard (the core invariant)"
bash scripts/guard-readonly.sh || rc=1

step "read-only UI/agenda guard (no write paths)"
bash scripts/guard-readonly-ui.sh || rc=1

step "node --check exporter"
node --check scripts/actual-export/export.js && echo "ok export.js" || rc=1

step "python compile ingester"
python3 -m py_compile scripts/email-ingester/parse_emails.py && echo "ok parse_emails.py" || rc=1

step "compose YAML valid"
python3 - <<'PY' || rc=1
import glob, yaml
for f in sorted(glob.glob("apps/deploy/docker-compose.*.yml")):
    yaml.safe_load(open(f)); print("ok", f)
PY

step "memory JSON valid"
python3 - <<'PY' || rc=1
import glob, json
for f in sorted(glob.glob("ai/memory/*.json")):
    json.load(open(f)); print("ok", f)
PY

step "shell scripts parse (bash -n)"
for s in "apps/deploy/deploy.sh" "apps/deploy/00-create-dirs.sh" \
         ai/load_context.sh scripts/guard-readonly.sh scripts/guard-readonly-ui.sh scripts/preflight.sh \
         scripts/backup/ifthe-backup.sh scripts/backup/ifthe-restore.sh scripts/check.sh; do
  bash -n "$s" && echo "ok $s" || rc=1
done

step "dashboard front-door + glance validity"
node --check "apps/dashboard/frontdoor/app.js" && echo "ok app.js" || rc=1
python3 - <<'PY' || rc=1
import json, yaml
json.load(open("apps/dashboard/frontdoor/apps.json")); print("ok apps.json")
yaml.safe_load(open("apps/dashboard/glance.yml")); print("ok glance.yml")
yaml.safe_load(open("apps/deploy/colima.example.yaml")); print("ok colima.example.yaml")
PY
python3 -m py_compile scripts/agenda-export/agenda_export.py && echo "ok agenda_export.py" || rc=1

echo
if [ "$rc" -eq 0 ]; then echo "ALL GATES PASS"; else echo "GATES FAILED"; fi
exit "$rc"
