#!/usr/bin/env node
/* Front door DOM behaviour test (quality loop pass 2).
 *
 * Serves the shipped front door (apps/dashboard/frontdoor) from three
 * local docroots and drives it in a real headless Chromium over CDP:
 *   A: full data, agenda with 8 events (one all-day, one untitled)
 *   B: empty agenda
 *   C: apps.json missing and no data dir (both failure states)
 *
 * The idle timer is the only thing the harness touches: a script
 * injected before app.js loads compresses the 180000 ms idle timeout
 * to 250 ms, the fake-timers technique. Every shipped function, event
 * listener, fetch, and render runs exactly as production.
 *
 * Checks print PASS/FAIL lines; exit 1 on any failure. Needs a Chromium
 * binary (same discovery as the image scripts: CHROME_BIN, PATH names,
 * then ~/workspace/tools/chrome-linux64/chrome).
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FRONTDOOR = path.join(ROOT, "apps", "dashboard", "frontdoor");
const CDP_PORT = 9341;

const results = [];
function check(name, cond, detail = "") { results.push([name, !!cond, detail]); }

function findChrome() {
  if (process.env.CHROME_BIN) return process.env.CHROME_BIN;
  for (const dir of (process.env.PATH || "").split(path.delimiter)) {
    for (const name of ["google-chrome", "chromium", "chromium-browser", "chrome"]) {
      const p = path.join(dir, name);
      try { fs.accessSync(p, fs.constants.X_OK); return p; } catch {}
    }
  }
  const local = path.join(os.homedir(), "workspace", "tools", "chrome-linux64", "chrome");
  if (fs.existsSync(local)) return local;
  return null;
}

function makeDocroot(tmp, variant) {
  const dir = fs.mkdtempSync(path.join(tmp, variant + "-"));
  for (const f of ["index.html", "app.js", "styles.css"]) {
    fs.copyFileSync(path.join(FRONTDOOR, f), path.join(dir, f));
  }
  if (variant !== "broken") {
    fs.copyFileSync(path.join(FRONTDOOR, "apps.json"), path.join(dir, "apps.json"));
    fs.mkdirSync(path.join(dir, "data"));
    const events = variant === "full" ? [
      { time: "7:00 AM", title: "Wake up" },
      { all_day: true, title: "Garbage day" },
      { time: "9:05 AM" },
      { time: "10:00 AM", title: "Dentist" },
      { time: "12:30 PM", title: "Lunch" },
      { time: "3:00 PM", title: "School run" },
      { time: "5:45 PM", title: "Gym" },
      { time: "7:30 PM", title: "Movie night" },
    ] : [];
    fs.writeFileSync(path.join(dir, "data", "agenda.json"),
      JSON.stringify({ date: "2026-11-25", events }));
  }
  return dir;
}

function serve(dir, port) {
  const proc = spawn("python3", ["-m", "http.server", String(port),
    "--bind", "127.0.0.1", "--directory", dir], { stdio: "ignore" });
  return proc;
}

async function waitFor(fn, timeoutMs, what) {
  const t0 = Date.now();
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() - t0 > timeoutMs) throw new Error("timeout waiting for " + what);
    await new Promise((r) => setTimeout(r, 100));
  }
}

// ---- minimal CDP client over the built-in WebSocket ----
class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.addEventListener("message", (m) => {
      const msg = JSON.parse(m.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message)); else resolve(msg.result);
      }
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expr) {
    const r = await this.send("Runtime.evaluate",
      { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) {
      throw new Error("page error: " + (r.exceptionDetails.exception?.description || expr));
    }
    return r.result.value;
  }
  until(expr, timeoutMs, what) {
    return waitFor(async () => (await this.eval(expr)) || null, timeoutMs, what);
  }
}

const TIMER_WRAP = `(() => {
  const st = window.setTimeout;
  window.setTimeout = function (fn, ms, ...rest) {
    if (ms === 180000) ms = 250;
    return st(fn, ms, ...rest);
  };
})();`;

async function main() {
  const chrome = findChrome();
  check("a Chromium binary is available", chrome !== null, "set CHROME_BIN");
  if (!chrome) return report();

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "fd-dom-"));
  const ports = { full: 8911, empty: 8912, broken: 8913 };
  const servers = [];
  const browser = spawn(chrome, ["--headless", "--no-sandbox", "--disable-gpu",
    "--no-proxy-server",
    "--remote-debugging-port=" + CDP_PORT,
    "--user-data-dir=" + path.join(tmp, "profile"), "about:blank"],
    { stdio: "ignore" });
  try {
    for (const [variant, port] of Object.entries(ports)) {
      servers.push(serve(makeDocroot(tmp, variant), port));
    }
    await waitFor(async () => {
      try { const r = await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`); return r.ok; }
      catch { return false; }
    }, 15000, "chrome CDP");

    const target = await (await fetch(
      `http://127.0.0.1:${CDP_PORT}/json/new?about:blank`, { method: "PUT" })).json();
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", rej); });
    const cdp = new CDP(ws);
    await cdp.send("Runtime.enable");
    await cdp.send("Page.enable");
    await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: TIMER_WRAP });

    const go = async (port) => {
      await cdp.send("Page.navigate", { url: `http://127.0.0.1:${port}/` });
    };
    const asleep = () => cdp.until(
      `document.getElementById('sleep').hidden === false`, 8000, "sleep screen");

    // ---- root A: full data ----
    await go(ports.full);
    await cdp.until(`document.querySelectorAll('#app-grid .card').length === 11`,
      8000, "launcher grid");
    check("launcher renders one card per apps.json entry (11)",
      await cdp.eval(`document.querySelectorAll('#app-grid .card').length`) === 11);
    check("card hrefs have {host} replaced by the page host",
      await cdp.eval(`document.querySelector('#app-grid .card').href.includes('127.0.0.1')
        && !document.querySelector('#app-grid .card').href.includes('{host}')`));
    check("cards open in a new tab with noopener",
      await cdp.eval(`(() => { const c = document.querySelector('#app-grid .card');
        return c.target === '_blank' && c.rel.includes('noopener'); })()`));
    check("the first card's icon is the app name's first letter",
      await cdp.eval(`document.querySelector('#app-grid .card .ico').textContent`) === "A");
    await asleep();
    check("the sleep screen shows after the idle period",
      await cdp.eval(`document.getElementById('sleep').hidden`) === false);
    check("aria-hidden tracks the sleep screen visibility",
      await cdp.eval(`document.getElementById('sleep').getAttribute('aria-hidden')`) === "false");
    check("the ambient clock shows a 12 hour time",
      /^\d{1,2}:\d{2}$/.test(await cdp.eval(`document.getElementById('s-time').textContent`)));
    check("the greeting is one of the four time-of-day lines",
      ["Good morning", "Good afternoon", "Good evening", "Good night"]
        .includes(await cdp.eval(`document.getElementById('s-greet').textContent`)));
    check("the agenda renders exactly 6 of the 8 events",
      await cdp.eval(`document.querySelectorAll('#s-agenda li').length`) === 6);
    check("an all-day event's time cell reads 'all day'",
      await cdp.eval(`document.querySelectorAll('#s-agenda li')[1].firstChild.textContent`) === "all day");
    check("an untitled event renders '(untitled)'",
      await cdp.eval(`document.querySelectorAll('#s-agenda li')[2].lastChild.textContent`) === "(untitled)");
    check("focus moves into the sleep region while asleep",
      await cdp.eval(`document.activeElement.id`) === "sleep");
    await cdp.eval(`window.dispatchEvent(new Event('pointerdown'))`);
    check("an interaction wakes the sleep screen",
      await cdp.eval(`document.getElementById('sleep').hidden`) === true);
    check("wake returns focus to the first app card",
      await cdp.eval(`document.activeElement.classList.contains('card')`));

    // ---- root B: empty agenda ----
    await go(ports.empty);
    await asleep();
    check("an empty agenda renders 'No events today'",
      await cdp.eval(`document.querySelector('#s-agenda li').textContent`) === "No events today");

    // ---- root C: apps.json missing, no data dir ----
    await go(ports.broken);
    await cdp.until(`document.getElementById('app-grid').textContent.includes('Could not load apps.json')`,
      8000, "apps fallback");
    check("a failed apps.json load shows the fallback line",
      await cdp.eval(`document.getElementById('app-grid').textContent.includes('Could not load apps.json. Edit it to list your services.')`));
    await asleep();
    check("a failed agenda fetch renders 'Agenda unavailable'",
      await cdp.eval(`document.querySelector('#s-agenda li').textContent`) === "Agenda unavailable");
    await cdp.eval(`window.dispatchEvent(new Event('keydown'))`);
    check("wake with no cards falls focus back to the body",
      await cdp.eval(`document.activeElement === document.body`));

    ws.close();
  } finally {
    browser.kill("SIGKILL");
    for (const s of servers) s.kill("SIGKILL");
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  report();
}

function report() {
  const fails = results.filter(([, ok]) => !ok);
  console.log(`\nfrontdoor_dom: ${results.length - fails.length}/${results.length} checks passed`);
  for (const [n, ok, d] of results) {
    console.log(`  ${ok ? "PASS" : "FAIL"}  ${n}` + (!ok && d ? `   [${d}]` : ""));
  }
  process.exit(fails.length ? 1 : 0);
}

main().catch((e) => { check("driver completed", false, String(e && e.message || e)); report(); });
