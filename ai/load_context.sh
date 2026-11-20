#!/usr/bin/env bash
# ============================================================
# ifthe :: load the full session context to stdout
# ------------------------------------------------------------
# Paste the output into a Claude session, or pipe it:
#   bash ai/load_context.sh | pbcopy
#   bash ai/load_context.sh | claude -p "Give me this month's get-back-on-track plan"
#
# Concatenates: the system prompt, all human-maintained memory files, and the
# latest read-only exports (ledger.json + parsed_emails.json) if present.
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DATA_ROOT="${DATA_ROOT:-/Users/Shared/ifthe}"

emit() {  # emit <label> <file>
  [ -f "$2" ] || return 0
  printf '\n===== %s =====\n' "$1"
  cat "$2"
}

echo "================ IFTHE :: SESSION CONTEXT ================"
emit "SYSTEM_PROMPT.md" "$HERE/SYSTEM_PROMPT.md"

# Human-maintained context (markdown first for narrative, then JSON facts).
for f in "$HERE"/memory/*.md "$HERE"/memory/*.json; do
  [ -e "$f" ] && emit "memory/$(basename "$f")" "$f"
done

# Read-only exports (may be absent until the exporters have run).
emit "ledger.json (exported budget data)"        "$DATA_ROOT/ai/ledger.json"
emit "parsed_emails.json (bills/receipts)"        "$DATA_ROOT/ai/parsed_emails.json"

printf '\n================ END CONTEXT ================\n'
