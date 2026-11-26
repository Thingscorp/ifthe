#!/usr/bin/env bash
# Behavioural tests for the ifthe shell scripts. No Docker required
# (a tiny `docker` shim is injected where a script insists on it).
# Run: bash tests/test_shell.sh
set -uo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1   [$2]"; }
# expect <rc> <desc> -- cmd...
expect(){ local want=$1 desc=$2; shift 3; local out rc; out=$("$@" 2>&1); rc=$?; if [ "$rc" -eq "$want" ]; then ok "$desc"; else no "$desc" "want rc=$want got rc=$rc"; fi; }

TMP=$(mktemp -d); trap '[ -f "$TMP/app.js.bak" ] && cp "$TMP/app.js.bak" apps/dashboard/frontdoor/app.js 2>/dev/null; rm -rf "$TMP" scripts/actual-export/__qa_tmp.js' EXIT
# docker shim that succeeds, for scripts that probe docker
mkdir -p "$TMP/bin"; printf '#!/bin/sh\nexit 0\n' > "$TMP/bin/docker"; chmod +x "$TMP/bin/docker"

echo "== guard-readonly.sh =="
expect 0 "guard passes on the clean tree" -- bash scripts/guard-readonly.sh
printf 'api.addTransactions([{}])\n' > scripts/actual-export/__qa_tmp.js
expect 1 "guard FAILS when a money-mutating call is injected" -- bash scripts/guard-readonly.sh
rm -f scripts/actual-export/__qa_tmp.js
expect 0 "guard passes again after the injected file is removed" -- bash scripts/guard-readonly.sh

echo "== guard-readonly-ui.sh =="
expect 0 "ui guard passes on the clean tree" -- bash scripts/guard-readonly-ui.sh
cp apps/dashboard/frontdoor/app.js "$TMP/app.js.bak"
printf '\nfetch("/x", {method: "POST"});\n' >> apps/dashboard/frontdoor/app.js
expect 1 "ui guard FAILS when a mutating fetch is injected into app.js" -- bash scripts/guard-readonly-ui.sh
cp "$TMP/app.js.bak" apps/dashboard/frontdoor/app.js
expect 0 "ui guard passes again after app.js is restored" -- bash scripts/guard-readonly-ui.sh

echo "== preflight.sh =="
SECRETS=(VW_ADMIN_TOKEN=x PAPERLESS_DB_PASS=x PAPERLESS_SECRET_KEY=x PAPERLESS_ADMIN_PASSWORD=x NEXTCLOUD_DB_ROOT_PASS=x NEXTCLOUD_DB_PASS=x NEXTCLOUD_ADMIN_PASSWORD=x HOMEBOX_API_KEY_PEPPER=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)
expect 0 "all secrets set + good DATA_ROOT -> ok" -- env DATA_ROOT=/srv/ifthe "${SECRETS[@]}" bash scripts/preflight.sh
expect 1 "DATA_ROOT on /Volumes (network mount) -> fail" -- env DATA_ROOT=/Volumes/usb "${SECRETS[@]}" bash scripts/preflight.sh
if [ "$(uname -s)" != "Darwin" ]; then
  expect 1 "macOS DATA_ROOT on a non-Mac host -> fail" -- env DATA_ROOT=/Users/Shared/ifthe "${SECRETS[@]}" bash scripts/preflight.sh
  mkdir -p "$TMP/fakebin"
  printf '#!/bin/sh\necho "tcp  LISTEN 0 4096 127.0.0.53:53 0.0.0.0:*"\n' > "$TMP/fakebin/ss"
  chmod +x "$TMP/fakebin/ss"
  expect 1 "systemd-resolved stub on port 53 -> fail" -- env PATH="$TMP/fakebin:$PATH" DATA_ROOT=/srv/ifthe "${SECRETS[@]}" bash scripts/preflight.sh
fi
expect 1 "empty required secret -> fail" -- env DATA_ROOT=/srv/ifthe VW_ADMIN_TOKEN= PAPERLESS_DB_PASS=x PAPERLESS_SECRET_KEY=x PAPERLESS_ADMIN_PASSWORD=x NEXTCLOUD_DB_ROOT_PASS=x NEXTCLOUD_DB_PASS=x NEXTCLOUD_ADMIN_PASSWORD=x HOMEBOX_API_KEY_PEPPER=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx bash scripts/preflight.sh
expect 1 "short HOMEBOX_API_KEY_PEPPER -> fail" -- env DATA_ROOT=/srv/ifthe "${SECRETS[@]}" HOMEBOX_API_KEY_PEPPER=short bash scripts/preflight.sh

echo "== preflight.sh warnings (warn, never fail) =="
# docker absent from PATH: symlink every core utility except docker/colima
# into a scratch bin dir, so `docker compose version` cannot succeed.
mkdir -p "$TMP/nodocker"
for f in /usr/bin/* /bin/*; do
  case "$(basename "$f")" in docker|colima) continue ;; esac
  ln -sf "$f" "$TMP/nodocker/" 2>/dev/null
done
out=$(env PATH="$TMP/nodocker" DATA_ROOT=/srv/ifthe "${SECRETS[@]}" bash scripts/preflight.sh 2>&1); rc=$?
if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -q "PREFLIGHT WARNING" && printf '%s' "$out" | grep -qi "docker compose"; then
  ok "docker compose missing -> exit 0 with a PREFLIGHT WARNING naming docker compose"
else
  no "docker compose missing -> exit 0 with a PREFLIGHT WARNING naming docker compose" "rc=$rc"
fi
# a colima executable on PATH + DATA_ROOT outside $HOME -> the Colima mount warning
mkdir -p "$TMP/colimabin"
printf '#!/bin/sh\nexit 0\n' > "$TMP/colimabin/colima"; chmod +x "$TMP/colimabin/colima"
out=$(env PATH="$TMP/colimabin:$PATH" DATA_ROOT=/srv/ifthe "${SECRETS[@]}" bash scripts/preflight.sh 2>&1); rc=$?
if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -q "PREFLIGHT WARNING: Colima detected" && printf '%s' "$out" | grep -q "DATA_ROOT='/srv/ifthe'"; then
  ok "colima present + DATA_ROOT outside \$HOME -> exit 0 with the Colima warning naming DATA_ROOT"
else
  no "colima present + DATA_ROOT outside \$HOME -> exit 0 with the Colima warning naming DATA_ROOT" "rc=$rc"
fi

echo "== 00-create-dirs.sh =="
expect 1 "refuses a /Volumes DATA_ROOT" -- env DATA_ROOT=/Volumes/usb/ifthe bash "apps/deploy/00-create-dirs.sh"
DR="$TMP/dataroot"
PATH="$TMP/bin:$PATH" DATA_ROOT="$DR" bash "apps/deploy/00-create-dirs.sh" >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 0 ] && [ -d "$DR/paperless/consume" ] && [ -d "$DR/nextcloud/data" ] && [ -d "$DR/ai" ] && [ -d "$DR/getmail/inbox/new" ]; then
  ok "creates the full dir tree (incl. nextcloud/data, ai, getmail/inbox) with docker present"
else
  no "creates the full dir tree" "rc=$rc; missing one of paperless/consume,nextcloud/data,ai,getmail/inbox/new"
fi

echo "== backup / restore (no-op safety without restic/docker) =="
# run with a PATH that has neither restic nor docker
BAREPATH="/usr/bin:/bin"
expect 0 "backup no-ops cleanly when DATA_ROOT unset" -- env -i PATH="$BAREPATH" bash scripts/backup/ifthe-backup.sh
expect 0 "backup no-ops cleanly when restic/docker absent" -- env -i PATH="$BAREPATH" DATA_ROOT="$DR" RESTIC_REPO="$TMP/repo" bash scripts/backup/ifthe-backup.sh
expect 0 "restore is a safe no-op by default (DRY_RUN / missing tools)" -- env -i PATH="$BAREPATH" DATA_ROOT="$DR" RESTIC_REPO="$TMP/repo" bash scripts/backup/ifthe-restore.sh

echo "== deploy.sh =="
( cd "$TMP" && mkdir d && cp "$OLDPWD/apps/deploy/deploy.sh" d/ ) 2>/dev/null
expect 1 "deploy.sh exits when no .env is present" -- bash -c 'cd "$1/d" && bash deploy.sh' _ "$TMP"

echo "== load_context.sh =="
out=$(DATA_ROOT="$TMP/none" bash ai/load_context.sh 2>&1); rc=$?
if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -q "IFTHE :: SESSION CONTEXT" && printf '%s' "$out" | grep -q "never move money"; then
  ok "emits session context (system prompt + memory), skips missing exports"
else
  no "emits session context" "rc=$rc"
fi

echo
echo "shell: $PASS passed, $FAIL failed"
exit $(( FAIL > 0 ? 1 : 0 ))
