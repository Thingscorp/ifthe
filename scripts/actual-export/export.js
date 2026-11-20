/**
 * Read-only Actual Budget exporter.
 *
 * Connects to a local Actual server, pulls accounts + categories +
 * transactions (rolling 13 months), and writes $DATA_ROOT/ai/ledger.json.
 *
 * Run:     node export.js
 * Cron:    0 6 * * * cd /path/to/actual-export && node export.js
 *
 * Never writes to Actual. Never touches bank credentials.
 * The output file is read-only input for Claude analysis sessions.
 */

import * as api from "@actual-app/api";
import fs from "fs";
import path from "path";

// ---- configuration ----------------------------------------------------------

const DATA_ROOT   = process.env.DATA_ROOT          || "/Users/Shared/ifthe";
const SERVER_URL  = process.env.ACTUAL_SERVER_URL  || "https://home.local:5006";
const SERVER_PASS = process.env.ACTUAL_SERVER_PASS;   // required
const BUDGET_ID   = process.env.ACTUAL_BUDGET_ID;     // required; the sync ID shown in Actual → Settings
const DATA_DIR    = process.env.ACTUAL_DATA_DIR  || "/tmp/actual-cache";
const OUT_FILE    = process.env.ACTUAL_OUT_FILE  || `${DATA_ROOT}/ai/ledger.json`;
const MONTHS_BACK = parseInt(process.env.ACTUAL_MONTHS_BACK || "13", 10);

if (!SERVER_PASS || !BUDGET_ID) {
  console.error("ACTUAL_SERVER_PASS and ACTUAL_BUDGET_ID must be set.");
  process.exit(1);
}

// ---- helpers ----------------------------------------------------------------

function isoMonth(offset = 0) {
  const d = new Date();
  d.setMonth(d.getMonth() + offset);
  return d.toISOString().slice(0, 7); // "YYYY-MM"
}

function todayISO() {
  return new Date().toISOString().slice(0, 10); // "YYYY-MM-DD"
}

// ---- main -------------------------------------------------------------------

async function main() {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });

  await api.init({ serverURL: SERVER_URL, password: SERVER_PASS, dataDir: DATA_DIR });

  try {
    await api.downloadBudget(BUDGET_ID);

    const [accounts, categories, payees] = await Promise.all([
      api.getAccounts(),
      api.getCategories(),
      api.getPayees(),
    ]);

    // Rolling window: startMonth .. current month
    const startMonth = isoMonth(-(MONTHS_BACK - 1));
    const endMonth   = isoMonth(0);

    const transactions = await api.getTransactions(
      undefined,            // all accounts (the API drops a falsy accountId filter)
      startMonth + "-01",
      todayISO(),           // today; avoids an invalid month-end like "-31" in 30-day months
    );

    // Strip internal fields the AI doesn't need; keep only useful analysis data.
    const txClean = transactions.map(t => ({
      id:         t.id,
      date:       t.date,
      account_id: t.account,
      payee_id:   t.payee,
      category_id:t.category,
      amount:     t.amount,    // milliunits (divide by 1000 for dollars)
      notes:      t.notes,
      cleared:    t.cleared,
      transfer_id:t.transfer_id || null,
    }));

    const ledger = {
      exported_at:    new Date().toISOString(),
      window_start:   startMonth,
      window_end:     endMonth,
      // getAccounts() returns { id, name, offbudget, closed, balance_current }.
      // balance_current can be null, so compute the real balance with getAccountBalance().
      accounts:       await Promise.all(accounts.map(async a => ({
        id:       a.id,
        name:     a.name,
        closed:   a.closed,
        balance:  await api.getAccountBalance(a.id),   // milliunits
        offbudget:a.offbudget,
      }))),
      categories:     categories.map(c => ({
        id:       c.id,
        name:     c.name,
        group_id: c.group_id,
        hidden:   c.hidden,
        is_income:c.is_income,
      })),
      payees:         payees.map(p => ({
        id:           p.id,
        name:         p.name,
        transfer_acct:p.transfer_acct || null,
      })),
      transactions:   txClean,
    };

    // 0600: the ledger holds household financials — owner-only, not world-readable.
    fs.writeFileSync(OUT_FILE, JSON.stringify(ledger, null, 2), { encoding: "utf8", mode: 0o600 });
    console.log(`Exported ${txClean.length} transactions → ${OUT_FILE}`);
  } finally {
    await api.shutdown();
  }
}

main().catch(err => {
  console.error("Export failed:", err);
  process.exit(1);
});
