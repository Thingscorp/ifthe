#!/usr/bin/env bash
# ifthe behavioural test suite (Phase 3/5 runner).
# Runs the static gate + the behavioural tests. Exit 0 only if all pass.
set -uo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
rc=0
run(){ printf '\n########## %s ##########\n' "$1"; shift; "$@" || rc=1; }

run "gate: scripts/check.sh"            bash scripts/check.sh
run "compose config contracts"          python3 tests/test_compose_contracts.py
run "parse_emails.py logic"             python3 tests/test_parse_emails.py
run "shell scripts behaviour"           bash tests/test_shell.sh
run "agenda exporter shaping"           python3 tests/test_agenda_export.py
run "front-door helpers"                node tests/test_frontdoor.js
run "dashboard config contracts"        python3 tests/test_dashboard_contracts.py
run "front-door security/a11y"          python3 tests/test_frontdoor_security.py
run "briefing widgets"                  python3 tests/test_briefing_widgets.py
run "gadget display JPEG"               python3 tests/test_display_jpeg.py
run "design token drift"                python3 tests/test_design_tokens.py

echo
if [ "$rc" -eq 0 ]; then echo "==== ALL TEST SUITES PASS ===="; else echo "==== TEST SUITES FAILED ===="; fi
exit "$rc"
