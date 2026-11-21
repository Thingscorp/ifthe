#!/usr/bin/env bash
# ============================================================
# ifthe :: backups (3-2-1)
# ------------------------------------------------------------
# Mirrors the "Backups (3-2-1)" section of apps/deploy/README.md:
#   1. restic snapshot of the bind-mounted data under $DATA_ROOT (caches excluded)
#   2. logical DB dumps (don't copy live DB files):
#        - Paperless (Postgres)  via  docker exec paperless-db pg_dump
#        - Nextcloud (MariaDB)    via  docker exec nextcloud-db mariadb-dump,
#          with occ maintenance:mode flipped on around the dump
#
# Read-only toward your money: this touches NOTHING financial: no bank, no
# SimpleFIN, no Actual. Back Actual up with its in-app Settings -> Export.
#
# Idempotent and safe to re-run (e.g. from cron/launchd). No-ops cleanly with a
# clear message and exit 0 if restic, docker, or the containers are absent, so
# it never errors on a box that doesn't have them.
#
#   DATA_ROOT=/Users/Shared/ifthe RESTIC_REPO=/Volumes/Backup/ifthe \
#     bash scripts/backup/ifthe-backup.sh
#
# Env:
#   DATA_ROOT    bind-mount root to snapshot + write dumps under (required)
#   RESTIC_REPO  restic repository path/URL (required for the restic step)
# restic also reads its password from RESTIC_PASSWORD / RESTIC_PASSWORD_FILE
# the same way the restic CLI does: this script does not handle the password.
# ============================================================
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-}"
RESTIC_REPO="${RESTIC_REPO:-}"

skip(){ echo "SKIP: $1"; }

if [ -z "$DATA_ROOT" ]; then
  echo "DATA_ROOT is not set: nothing to back up. Set DATA_ROOT (and RESTIC_REPO)."
  exit 0
fi

# --- 1. restic snapshot of the bind-mounted data ------------------------------
if ! command -v restic >/dev/null 2>&1; then
  skip "restic not installed: skipping the data snapshot."
elif [ -z "$RESTIC_REPO" ]; then
  skip "RESTIC_REPO not set: skipping the data snapshot."
elif [ ! -d "$DATA_ROOT" ]; then
  skip "DATA_ROOT '$DATA_ROOT' does not exist: skipping the data snapshot."
else
  echo "==> restic snapshot of $DATA_ROOT (caches excluded)"
  # Idempotent init: only create the repo if it isn't one already.
  if ! restic -r "$RESTIC_REPO" cat config >/dev/null 2>&1; then
    echo "    initialising restic repository at $RESTIC_REPO"
    restic -r "$RESTIC_REPO" init
  fi
  restic -r "$RESTIC_REPO" backup "$DATA_ROOT" \
    --exclude "$DATA_ROOT/**/cache"
fi

# --- 2. logical database dumps ------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  skip "docker not installed: skipping database dumps."
  echo "Done."
  exit 0
fi

# True only if a container with this exact name is currently running.
running(){ docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$1"; }

today="$(date +%F)"

# Paperless (Postgres): logical dump, never a copy of the live files.
if running paperless-db; then
  echo "==> paperless: pg_dump -> $DATA_ROOT/paperless/export/pg-$today.sql"
  mkdir -p "$DATA_ROOT/paperless/export"
  docker exec paperless-db pg_dump -U paperless paperless \
    > "$DATA_ROOT/paperless/export/pg-$today.sql"
else
  skip "paperless-db container not running: skipping Postgres dump."
fi

# Nextcloud (MariaDB): maintenance mode around the dump, per the README.
if running nextcloud-db; then
  echo "==> nextcloud: mariadb-dump -> $DATA_ROOT/nextcloud/db-$today.sql"
  mkdir -p "$DATA_ROOT/nextcloud"
  # Maintenance mode is best-effort: only when the app container is up.
  if running nextcloud; then
    docker exec nextcloud nextcloud occ maintenance:mode --on || true
  fi
  docker exec nextcloud-db sh -c 'mariadb-dump -u root -p"$MARIADB_ROOT_PASSWORD" nextcloud' \
    > "$DATA_ROOT/nextcloud/db-$today.sql"
  if running nextcloud; then
    docker exec nextcloud nextcloud occ maintenance:mode --off || true
  fi
else
  skip "nextcloud-db container not running: skipping MariaDB dump."
fi

echo "Done."
