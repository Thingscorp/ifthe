#!/usr/bin/env python3
"""Static security-posture checks for the ifthe front door (no Docker, no network).

Asserts:
  1. The dashboard Caddyfile sets X-Content-Type-Options, X-Frame-Options, Referrer-Policy.
  2. index.html ships a Content-Security-Policy meta with default-src 'self'.
  3. app.js performs no state-changing fetches (no POST/PUT/DELETE): read-only only.
"""
import re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FRONTDOOR = REPO / "apps" / "dashboard" / "frontdoor"
CADDYFILE = (REPO / "apps" / "dashboard" / "Caddyfile").read_text()
INDEX = (FRONTDOOR / "index.html").read_text()
APP_JS = (FRONTDOOR / "app.js").read_text()

results = []
def check(name, cond, detail=""): results.append((name, bool(cond), detail))

# ---- 1. Caddyfile security headers ----
check("Caddyfile sets X-Content-Type-Options", "X-Content-Type-Options" in CADDYFILE)
check("Caddyfile sets X-Frame-Options", "X-Frame-Options" in CADDYFILE)
check("Caddyfile sets Referrer-Policy", "Referrer-Policy" in CADDYFILE)
check("Caddyfile sets Permissions-Policy", "Permissions-Policy" in CADDYFILE)
check("Permissions-Policy disables geolocation, microphone, camera",
      all(s in CADDYFILE for s in ("geolocation=()", "microphone=()", "camera=()")))
check("Caddyfile removes the Server header", "-Server" in CADDYFILE)
check("Caddyfile enables gzip encoding", "encode gzip" in CADDYFILE)

# ---- 2. index.html locked-down CSP ----
# The content="..." value embeds single quotes (e.g. 'self'), so capture a
# double-quoted attribute value and let it contain single quotes verbatim.
csp = re.search(
    r'<meta[^>]*http-equiv=["\']Content-Security-Policy["\'][^>]*content="([^"]*)"',
    INDEX, re.I,
)
check("index.html has Content-Security-Policy meta", csp is not None)
check("CSP declares default-src 'self'",
      csp is not None and "default-src 'self'" in csp.group(1),
      "" if csp is None else csp.group(1))
# The remaining directives the shipped CSP actually declares (read from
# index.html): script-src, connect-src, base-uri, form-action, frame-ancestors.
csp_body = csp.group(1) if csp is not None else ""
check("CSP declares script-src 'self'", "script-src 'self'" in csp_body)
check("CSP declares connect-src 'self'", "connect-src 'self'" in csp_body)
check("CSP declares base-uri", "base-uri" in csp_body)
check("CSP declares form-action", "form-action" in csp_body)
check("CSP declares frame-ancestors", "frame-ancestors" in csp_body)

# ---- 3. app.js is read-only (no state-changing fetch) ----
# Flag any fetch() whose options object names a mutating HTTP method.
mutating = re.findall(r'method\s*:\s*["\'](POST|PUT|DELETE|PATCH)["\']', APP_JS, re.I)
check("app.js has no POST/PUT/DELETE fetch", not mutating,
      ("found: " + ", ".join(mutating)) if mutating else "")

passed = sum(1 for _, ok, _ in results if ok)
fails = [(n, d) for n, ok, d in results if not ok]
print(f"\nfrontdoor_security: {passed}/{len(results)} checks passed")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}" + (f"   [{d}]" if (not ok and d) else ""))
sys.exit(1 if fails else 0)
