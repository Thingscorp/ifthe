#!/usr/bin/env bash
# ============================================================
# ifthe :: restore (companion to ifthe-backup.sh)
# ------------------------------------------------------------
# Reverses ifthe-backup.sh, in the same order the README documents:
#   1. restic restore of the latest snapshot of $DATA_ROOT (into RESTORE_TARGET)
#   2. logical DB loads (feed the dumps back in; never copy live DB files):
#        - Paperless (Postgres)  via  docker exec -i paperless-db psql
#        - Nextcloud (MariaDB)    via  docker exec -i nextcloud-db mariadb,
#          with occ maintenance:mode flipped on around the load
#
# Read-only toward your money: this touches NOTHING financial — no bank, no
# SimpleFIN, no Actual. Restore Actual from its in-app Settings -> Import.
#
# Safe to re-run. No-ops cleanly with a clear message and exit 0 if restic,
# docker, or the containers are absent, so it never errors on a box without them.
#
# This is destructive by design: it overwrites RESTORE_TARGET and DB contents.
# It DRY-RUNS by default and only does real work when DRY_RUN=0, so it never
# clobbers silently.
#
#   DATA_ROOT=/Users/Shared/ifthe RESTIC_REPO=/Volumes/Backup/ifthe \
#     DRY_RUN=0 bash scripts/backup/ifthe-restore.sh
#
# Env:
#   DATA_ROOT      bind-mount root the dumps live under (required)
#   RESTIC_REPO    restic repository path/URL (required for the restic step)
#   RESTORE_TARGET where restic writes the restored tree (default: $DATA_ROOT)
#   DRY_RUN        1 (default) = show what would happen; 0 = actually restore
# restic also reads its password from RESTIC_PASSWORD / RESTIC_PASSWORD_FILE
# the same way the restic CLI does — this script does not handle the password.
# ============================================================
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-}"
RESTIC_REPO="${RESTIC_REPO:-}"
RESTORE_TARGET="${RESTORE_TARGET:-$DATA_ROOT}"
DRY_RUN="${DRY_RUN:-1}"

skip(){ echo "SKIP: $1"; }

if [ -z "$DATA_ROOT" ]; then
  echo "DATA_ROOT is not set — nothing to restore. Set DATA_ROOT (and RESTIC_REPO)."
  exit 0
fi

if [ "$DRY_RUN" != "0" ]; then
  echo "DRY RUN (DRY_RUN=$DRY_RUN): showing what would be restored without changing anything."
  echo "         Re-run with DRY_RUN=0 to actually restore (this overwrites data)."
fi

# Newest file matching a glob, or empty if none. Used to find the latest dump.
newest(){ ls -1t $1 2>/dev/null | head -n 1; }

# --- 1. restic restore of the latest snapshot --------------------------------
if ! command -v restic >/dev/null 2>&1; then
  skip "restic not installed — skipping the data restore."
elif [ -z "$RESTIC_REPO" ]; then
  skip "RESTIC_REPO not set — skipping the data restore."
elif ! restic -r "$RESTIC_REPO" cat config >/dev/null 2>&1; then
  skip "no restic repository at $RESTIC_REPO — skipping the data restore."
else
  echo "==> restic restore latest snapshot -> $RESTORE_TARGET"
  if [ "$DRY_RUN" != "0" ]; then
    echo "    would run: restic -r $RESTIC_REPO restore latest --target $RESTORE_TARGET"
  else
    restic -r "$RESTIC_REPO" restore latest --target "$RESTORE_TARGET"
  fi
fi

# --- 2. logical database loads ------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  skip "docker not installed — skipping database loads."
  echo "Done."
  exit 0
fi

# True only if a container with this exact name is currently running.
running(){ docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$1"; }

# Paperless (Postgres) — load the newest logical dump back in.
if running paperless-db; then
  pg_dump_file="$(newest "$DATA_ROOT/paperless/export/pg-*.sql")"
  if [ -z "$pg_dump_file" ]; then
    skip "no $DATA_ROOT/paperless/export/pg-*.sql dump found — skipping Postgres restore."
  else
    echo "==> paperless: psql < $pg_dump_file"
    if [ "$DRY_RUN" != "0" ]; then
      echo "    would run: docker exec -i paperless-db psql -U paperless paperless < $pg_dump_file"
    else
      docker exec -i paperless-db psql -U paperless paperless < "$pg_dump_file"
    fi
  fi
else
  skip "paperless-db container not running — skipping Postgres restore."
fi

# Nextcloud (MariaDB) — maintenance mode around the load, per the README.
if running nextcloud-db; then
  db_dump_file="$(newest "$DATA_ROOT/nextcloud/db-*.sql")"
  if [ -z "$db_dump_file" ]; then
    skip "no $DATA_ROOT/nextcloud/db-*.sql dump found — skipping MariaDB restore."
  else
    echo "==> nextcloud: mariadb < $db_dump_file"
    if [ "$DRY_RUN" != "0" ]; then
      echo "    would run: occ maintenance:mode --on; docker exec -i nextcloud-db mariadb ... nextcloud < $db_dump_file; occ maintenance:mode --off"
    else
      # Maintenance mode is best-effort: only when the app container is up.
      if running nextcloud; then
        docker exec nextcloud nextcloud occ maintenance:mode --on || true
      fi
      docker exec -i nextcloud-db sh -c 'mariadb -u root -p"$MARIADB_ROOT_PASSWORD" nextcloud' \
        < "$db_dump_file"
      if running nextcloud; then
        docker exec nextcloud nextcloud occ maintenance:mode --off || true
      fi
    fi
  fi
else
  skip "nextcloud-db container not running — skipping MariaDB restore."
fi

echo "Done."
