#!/usr/bin/env bash
# ============================================================
# ifthe :: pre-deploy safety checks
# ------------------------------------------------------------
# Run AFTER .env has been sourced (set -a; source .env; set +a),
# BEFORE creating the directory tree / bringing stacks up.
#
# FAILS (nonzero exit) if:
#   - DATA_ROOT is unset
#   - DATA_ROOT lives under /Volumes/* (must be a LOCAL disk, never SMB/NFS)
#   - any required secret is empty
# WARNS (does not fail) if docker compose is missing.
# ============================================================
set -euo pipefail

fail() { echo "PREFLIGHT FAILED: $*" >&2; exit 1; }

# DATA_ROOT must be set and on a local disk.
if [ -z "${DATA_ROOT:-}" ]; then
  fail "DATA_ROOT is not set. Fill it in .env (e.g. /Users/Shared/ifthe)."
fi
case "$DATA_ROOT" in
  /Volumes/*)
    fail "DATA_ROOT='$DATA_ROOT' is under /Volumes (a mounted/network share). SQLite + databases MUST live on a LOCAL disk. Edit DATA_ROOT and retry." ;;
esac

# Colima (your home server's runtime) mounts $HOME by default but NOT /Users/Shared. If DATA_ROOT is
# outside $HOME, bind mounts will be EMPTY inside containers unless you've added a Colima
# mount for it. Warn (don't fail — you may have added the mount via `colima start --edit`).
if command -v colima >/dev/null 2>&1; then
  case "$DATA_ROOT" in
    "${HOME:-/nonexistent}"/*) : ;;
    *) echo "PREFLIGHT WARNING: Colima detected and DATA_ROOT='$DATA_ROOT' is outside \$HOME ($HOME). Colima only mounts paths it's told to — add '- location: $DATA_ROOT' (writable: true) via 'colima start --edit' or bind mounts will be EMPTY in containers. See colima.example.yaml." >&2 ;;
  esac
fi

# Every required secret must be non-empty.
required_secrets=(
  VW_ADMIN_TOKEN
  PAPERLESS_DB_PASS
  PAPERLESS_SECRET_KEY
  PAPERLESS_ADMIN_PASSWORD
  NEXTCLOUD_DB_ROOT_PASS
  NEXTCLOUD_DB_PASS
  NEXTCLOUD_ADMIN_PASSWORD
)
for var in "${required_secrets[@]}"; do
  if [ -z "${!var:-}" ]; then
    fail "$var is empty. Set it in .env (generate with: openssl rand -base64 48)."
  fi
done

# Docker Compose is needed to bring stacks up, but only warn here so this
# script can be sanity-run on a box without Docker installed yet.
if ! docker compose version >/dev/null 2>&1; then
  echo "PREFLIGHT WARNING: 'docker compose' not found. Install Docker before deploying." >&2
fi

echo "✓ Preflight checks passed"
