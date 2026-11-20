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

TMP=$(mktemp -d); trap 'rm -rf "$TMP" scripts/actual-export/__qa_tmp.js' EXIT
# docker shim that succeeds, for scripts that probe docker
mkdir -p "$TMP/bin"; printf '#!/bin/sh\nexit 0\n' > "$TMP/bin/docker"; chmod +x "$TMP/bin/docker"

echo "== guard-readonly.sh =="
expect 0 "guard passes on the clean tree" -- bash scripts/guard-readonly.sh
printf 'api.addTransactions([{}])\n' > scripts/actual-export/__qa_tmp.js
expect 1 "guard FAILS when a money-mutating call is injected" -- bash scripts/guard-readonly.sh
rm -f scripts/actual-export/__qa_tmp.js
expect 0 "guard passes again after the injected file is removed" -- bash scripts/guard-readonly.sh

echo "== preflight.sh =="
SECRETS=(VW_ADMIN_TOKEN=x PAPERLESS_DB_PASS=x PAPERLESS_SECRET_KEY=x PAPERLESS_ADMIN_PASSWORD=x NEXTCLOUD_DB_ROOT_PASS=x NEXTCLOUD_DB_PASS=x NEXTCLOUD_ADMIN_PASSWORD=x)
expect 0 "all secrets set + good DATA_ROOT -> ok" -- env DATA_ROOT=/Users/Shared/ifthe "${SECRETS[@]}" bash scripts/preflight.sh
expect 1 "DATA_ROOT on /Volumes (network mount) -> fail" -- env DATA_ROOT=/Volumes/usb "${SECRETS[@]}" bash scripts/preflight.sh
expect 1 "empty required secret -> fail" -- env DATA_ROOT=/Users/Shared/ifthe VW_ADMIN_TOKEN= PAPERLESS_DB_PASS=x PAPERLESS_SECRET_KEY=x PAPERLESS_ADMIN_PASSWORD=x NEXTCLOUD_DB_ROOT_PASS=x NEXTCLOUD_DB_PASS=x NEXTCLOUD_ADMIN_PASSWORD=x bash scripts/preflight.sh

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
