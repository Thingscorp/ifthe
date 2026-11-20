#!/usr/bin/env bash
# ============================================================
# ifthe :: read-only guard
# ------------------------------------------------------------
# Fails if any money-mutating @actual-app/api call appears in the exporter.
# Makes the "never move money" guarantee structural, not just conventional.
# Run manually or as a pre-commit / CI check:
#   bash scripts/guard-readonly.sh
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

FORBIDDEN='api\.(addTransactions|importTransactions|updateTransaction|deleteTransaction|createAccount|updateAccount|closeAccount|deleteAccount|createCategory|updateCategory|deleteCategory|createCategoryGroup|updateCategoryGroup|deleteCategoryGroup|createPayee|updatePayee|deletePayee|mergePayees|runBankSync|setBudgetAmount|setBudgetCarryover|batchBudgetUpdates|runQuery|aqlQuery)'

if grep -rnE "$FORBIDDEN" "$HERE/actual-export" --include='*.js' --include='*.mjs' 2>/dev/null; then
  echo >&2
  echo "READ-ONLY VIOLATION: a money-mutating Actual API call is present above." >&2
  echo "The exporter must call ONLY read methods. Remove it." >&2
  exit 1
fi

echo "✓ read-only guard passed (no mutating Actual API calls in scripts/actual-export)"
