#!/usr/bin/env bash
# ============================================================
# ifthe :: one-shot deploy
# ------------------------------------------------------------
# Brings the whole suite up in order on your home server.
#
#   bash deploy.sh            # foundation + docs + family
#   bash deploy.sh --with-ai  # also build + start the read-only AI exporters
#
# Re-runnable. Assumes Docker is installed and running.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "No .env found. Copy .env.example to .env and fill it in first:" >&2
  echo "  cp .env.example .env" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 not found. Install Docker first (Docker Desktop on macOS)." >&2
  exit 1
fi

set -a; source .env; set +a

echo "==> running preflight safety checks"
bash ../../scripts/preflight.sh

echo "==> creating directory tree + ifthe_net"
bash 00-create-dirs.sh

for stack in foundation docs family; do
  echo "==> bringing up $stack"
  docker compose -f "docker-compose.$stack.yml" up -d
done

if [ "${1:-}" = "--with-ai" ]; then
  echo "==> building + starting AI exporters (read-only)"
  docker compose -f docker-compose.ai.yml up -d --build
fi

echo
echo "All stacks are up. Check status with:"
echo "  docker compose -f docker-compose.foundation.yml ps"
echo "Reach services per the table in README.md (LAN). Vaultwarden is localhost-only"
echo "until you expose it over HTTPS via Tailscale Serve."
