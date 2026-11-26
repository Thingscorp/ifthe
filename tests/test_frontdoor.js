// Tests for the front-door pure helpers. app.js exports them in node (module.exports)
// and bails before any DOM code when `document` is undefined.
const path = require("path");
const m = require(path.join(__dirname, "..", "apps", "dashboard", "frontdoor", "app.js"));

let pass = 0, fail = 0;
function ok(name, cond) { if (cond) { pass++; console.log("  PASS  " + name); } else { fail++; console.log("  FAIL  " + name); } }

ok("greeting 2am -> night", m.greeting(2) === "Good night");
ok("greeting 9am -> morning", m.greeting(9) === "Good morning");
ok("greeting 2pm -> afternoon", m.greeting(14) === "Good afternoon");
ok("greeting 7pm -> evening", m.greeting(19) === "Good evening");
ok("greeting 11pm -> night", m.greeting(23) === "Good night");
ok("greeting 4am -> night (boundary)", m.greeting(4) === "Good night");
ok("greeting 5am -> morning (boundary)", m.greeting(5) === "Good morning");
ok("greeting 12pm -> afternoon (boundary)", m.greeting(12) === "Good afternoon");
ok("greeting 5pm -> evening (boundary)", m.greeting(17) === "Good evening");
ok("greeting 9pm -> night (boundary)", m.greeting(21) === "Good night");
const nov21 = m.fmtDate(new Date(2026, 10, 21));
ok("fmtDate 2026-11-21 -> non-empty string containing 21",
   typeof nov21 === "string" && nov21.length > 0 && nov21.includes("21"));
ok("fmtTime 9:05", m.fmtTime(new Date(2025, 0, 1, 9, 5)) === "9:05");
ok("fmtTime midnight -> 12:00", m.fmtTime(new Date(2025, 0, 1, 0, 0)) === "12:00");
ok("fmtTime 13:07 -> 1:07", m.fmtTime(new Date(2025, 0, 1, 13, 7)) === "1:07");
ok("appUrl host substitution", m.appUrl("https://{host}:5006", "home.local") === "https://home.local:5006");
ok("appUrl multi-token", m.appUrl("{host}/{host}", "x") === "x/x");

console.log(`\nfront-door: ${pass} passed, ${fail} failed`);
process.exit(fail > 0 ? 1 : 0);
