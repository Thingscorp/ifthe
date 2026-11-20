#!/usr/bin/env bash
# ============================================================
# ifthe :: read-only UI / agenda guard
# ------------------------------------------------------------
# Fails if the dashboard front door or the agenda exporter gains a
# write-capable code path:
#   - front door app.js: a fetch() with a mutating method, XMLHttpRequest,
#     navigator.sendBeacon, or a form submit / <form>.
#   - agenda exporter: any CalDAV write (.save / .add_event / .add_todo /
#     .delete / .put / mkcalendar).
# Keeps the "front door only reads, agenda never writes the calendar"
# guarantee structural, not just conventional.
# Run manually or as a pre-commit / CI check:
#   bash scripts/guard-readonly-ui.sh
# ============================================================
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

UI="$ROOT/apps/dashboard/frontdoor/app.js"
AGENDA="$ROOT/scripts/agenda-export/agenda_export.py"

fail=0

# ---- front door: must never make a write-capable request ----
# fetch(...) with method: POST/PUT/PATCH/DELETE (any quote/spacing/case).
UI_FETCH='method["'"'"']?[[:space:]]*:[[:space:]]*["'"'"'](POST|PUT|PATCH|DELETE)'
# XMLHttpRequest, navigator.sendBeacon, or a form submit / <form>.
UI_OTHER='XMLHttpRequest|navigator\.sendBeacon|sendBeacon\(|\.submit\(|<form'

if [ -f "$UI" ]; then
  if grep -rnEi "$UI_FETCH|$UI_OTHER" "$UI" 2>/dev/null; then
    echo >&2
    echo "READ-ONLY VIOLATION: front door app.js has a write-capable request above." >&2
    echo "  $UI" >&2
    fail=1
  fi
else
  echo "READ-ONLY VIOLATION: missing $UI" >&2
  fail=1
fi

# ---- agenda exporter: must never write to the calendar ----
AGENDA_WRITE='\.save\(|\.add_event|\.add_todo|\.delete\(|\.put\(|mkcalendar'

if [ -f "$AGENDA" ]; then
  if grep -rnE "$AGENDA_WRITE" "$AGENDA" 2>/dev/null; then
    echo >&2
    echo "READ-ONLY VIOLATION: agenda exporter has a CalDAV write above." >&2
    echo "  $AGENDA" >&2
    fail=1
  fi
else
  echo "READ-ONLY VIOLATION: missing $AGENDA" >&2
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo >&2
  echo "These paths must stay read-only (no money, no calendar writes). Remove the offending code." >&2
  exit 1
fi

echo "✓ read-only UI guard passed (front door app.js makes no write requests; agenda exporter does no CalDAV writes)"
