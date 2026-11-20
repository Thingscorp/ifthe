# Actual Budget Exporter

Read-only Node.js script that pulls your Actual Budget data and writes
`$DATA_ROOT/ai/ledger.json` for Claude analysis sessions to consume.

## Two ways to run it

- **Containerized (recommended):** `docker compose -f "apps/deploy/docker-compose.ai.yml" up -d --build`
  runs it on a daily loop. Set `ACTUAL_SERVER_PASS` and `ACTUAL_BUDGET_ID` in the
  deploy `.env`. Nothing to install on the host.
- **Directly (cron / one-off):** the steps below.

## Setup (direct)

```bash
cd scripts/actual-export
npm install

# Set environment variables (add to .env or ~/.zshrc on your home server):
export DATA_ROOT="/Users/Shared/ifthe"        # macOS; /srv/ifthe on Linux
export ACTUAL_SERVER_URL="https://home.local:5006"
export ACTUAL_SERVER_PASS="your-actual-server-password"
export ACTUAL_BUDGET_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  # Actual → Settings → Advanced → Sync ID
export ACTUAL_DATA_DIR="/tmp/actual-cache"       # temp cache dir; NOT your Actual data
# ACTUAL_OUT_FILE defaults to $DATA_ROOT/ai/ledger.json — override only if needed.
```

## Run once

```bash
node export.js
```

## Run on a schedule (cron on your home server)

```
# Every day at 6 AM — edit with: crontab -e
0 6 * * * cd /Users/Shared/scripts/actual-export && node export.js >> /tmp/actual-export.log 2>&1
```

## What gets written

`ledger.json` contains:

- All accounts (name, current balance in milliunits, on/off-budget, closed flag)
- All categories and category groups
- All payees
- Rolling 13 months of transactions (id, date, account, category, payee, amount, notes)

**Amount encoding:** Actual stores amounts as milliunits (integers). `$12.34` is stored
as `12340`. Divide by `1000` to get dollars, or ask Claude to do it.

## What does NOT get written

- Passwords, bank credentials, or SimpleFIN tokens — those never leave Actual.
- Budget allocations or envelope amounts (use Actual's built-in export for those).
- The underlying SQLite database — this reads via the API, not raw files.

## Security

The exporter calls **only read methods** from `@actual-app/api` (enforced by
`scripts/guard-readonly.sh`). It writes `ledger.json` with mode `0600` (owner-only)
since it holds household financials — keep `$DATA_ROOT/ai` at `0700`. Never put this
file on a network share or sync it to a cloud service.
