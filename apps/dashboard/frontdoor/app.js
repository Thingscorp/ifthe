/* ifthe front door: config-driven launcher + idle->bento sleep screen.
 * Strictly read-only — no writes, no POST, no money. Same-origin only (CSP). */
(function () {
  "use strict";

  // ---- pure helpers (also exported for node tests) ----
  function greeting(h) {
    if (h < 5) return "Good night";
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    if (h < 21) return "Good evening";
    return "Good night";
  }
  function fmtTime(d) {
    var h = d.getHours() % 12 || 12;
    return h + ":" + String(d.getMinutes()).padStart(2, "0");
  }
  function fmtDate(d) {
    return d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  }
  function appUrl(template, host) {
    return String(template || "").replace(/\{host\}/g, host);
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { greeting: greeting, fmtTime: fmtTime, fmtDate: fmtDate, appUrl: appUrl };
  }
  if (typeof document === "undefined") return; // imported in node for tests — stop before DOM code

  var IDLE_MS = 3 * 60 * 1000; // fade to the sleep screen after 3 min of no interaction
  var host = location.hostname || "home.local";

  // ---- launcher (from apps.json) ----
  function renderApps(apps) {
    var grid = document.getElementById("app-grid");
    grid.innerHTML = "";
    (apps || []).forEach(function (a) {
      var card = document.createElement("a");
      card.className = "card"; card.setAttribute("role", "listitem");
      card.href = appUrl(a.url, host);
      card.target = "_blank"; card.rel = "noopener noreferrer";
      card.setAttribute("aria-label", a.name + (a.desc ? " — " + a.desc : ""));
      var ic = document.createElement("span");
      ic.className = "ico"; ic.setAttribute("aria-hidden", "true");
      if (a.accent) ic.style.setProperty("--accent", a.accent);
      ic.textContent = (a.name || "?").trim().charAt(0).toUpperCase();
      var txt = document.createElement("span"); txt.className = "card-txt";
      var t = document.createElement("span"); t.className = "card-t"; t.textContent = a.name;
      var d = document.createElement("span"); d.className = "card-d muted"; d.textContent = a.desc || "";
      txt.appendChild(t); txt.appendChild(d);
      card.appendChild(ic); card.appendChild(txt);
      grid.appendChild(card);
    });
  }
  fetch("apps.json", { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw 0; return r.json(); })
    .then(renderApps)
    .catch(function () {
      document.getElementById("app-grid").innerHTML =
        '<p class="muted">Could not load apps.json — edit it to list your services.</p>';
    });

  // ---- ambient clock ----
  function tickClock() {
    var d = new Date();
    document.getElementById("s-time").textContent = fmtTime(d);
    document.getElementById("s-date").textContent = fmtDate(d);
    document.getElementById("s-greet").textContent = greeting(d.getHours()) + ", ifthes";
  }

  // ---- today's agenda (read-only export) ----
  function renderAgenda() {
    var ul = document.getElementById("s-agenda");
    fetch("data/agenda.json", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (data) {
        var ev = (data && data.events) || [];
        if (!ev.length) { ul.innerHTML = '<li class="muted">No events today</li>'; return; }
        ul.innerHTML = "";
        ev.slice(0, 6).forEach(function (e) {
          var li = document.createElement("li");
          var tm = document.createElement("span"); tm.className = "ag-t";
          tm.textContent = e.all_day ? "all day" : (e.time || "");
          var ti = document.createElement("span"); ti.textContent = e.title || "(untitled)";
          li.appendChild(tm); li.appendChild(ti); ul.appendChild(li);
        });
      })
      .catch(function () { ul.innerHTML = '<li class="muted">Agenda unavailable</li>'; });
  }

  // ---- idle detection ----
  var sleep = document.getElementById("sleep");
  var timer = null, asleep = false;
  function showSleep() {
    if (asleep) return;
    asleep = true; tickClock(); renderAgenda();
    sleep.hidden = false; sleep.setAttribute("aria-hidden", "false");
    sleep.focus(); // move keyboard focus into the sleep region
  }
  function wake() {
    asleep = false; sleep.hidden = true; sleep.setAttribute("aria-hidden", "true");
    // restore focus to a sensible launcher element (first app card, else body)
    var first = document.querySelector("#app-grid .card") || document.body;
    if (first && typeof first.focus === "function") first.focus();
    arm();
  }
  function arm() { if (timer) clearTimeout(timer); timer = setTimeout(showSleep, IDLE_MS); }

  ["pointerdown", "pointermove", "keydown", "wheel", "touchstart"].forEach(function (ev) {
    window.addEventListener(ev, function () { asleep ? wake() : arm(); }, { passive: true });
  });
  setInterval(function () { if (asleep) tickClock(); }, 10000);
  arm();
})();
