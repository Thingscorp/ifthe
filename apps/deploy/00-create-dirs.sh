#!/usr/bin/env bash
# ============================================================
# ifthe :: create the local-disk directory tree
# ------------------------------------------------------------
# Usage:
#   set -a && source .env && set +a && bash 00-create-dirs.sh
#
# Re-runnable (safe to run again). Creates only what's missing,
# then ensures the shared Docker network exists.
# ============================================================
set -euo pipefail

: "${DATA_ROOT:?DATA_ROOT is not set. Run: set -a && source .env && set +a}"

# Guard-rail: refuse to build the tree on a network mount.
case "$DATA_ROOT" in
  /Volumes/*|*/mnt/*|*/net/*)
    echo "WARNING: '$DATA_ROOT' looks like it may be a mounted/network share." >&2
    echo "SQLite + databases MUST live on a LOCAL disk. Edit DATA_ROOT and retry." >&2
    exit 1 ;;
esac

dirs=(
  vaultwarden
  adguard/work adguard/conf
  uptime-kuma
  paperless/data paperless/media paperless/export paperless/consume
  stirling/configs stirling/tessdata
  nextcloud/data
  wallos/db wallos/logos
  mealie/data
  homebox/data
  ai
  getmail/inbox/new getmail/inbox/cur getmail/inbox/tmp
  dashboard
)

for d in "${dirs[@]}"; do
  mkdir -p "$DATA_ROOT/$d"
done

# The ai/ dir holds ledger.json + parsed_emails.json (household financials).
# Owner-only so other local accounts / containers can't read it.
chmod 700 "$DATA_ROOT/ai" 2>/dev/null || true
echo "✓ Directory tree ready under: $DATA_ROOT"

# Shared network so services (and Uptime Kuma) can reach each other by name.
if docker network inspect ifthe_net >/dev/null 2>&1; then
  echo "✓ Docker network 'ifthe_net' already exists"
else
  docker network create ifthe_net >/dev/null
  echo "✓ Created Docker network 'ifthe_net'"
fi
