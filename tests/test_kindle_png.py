#!/usr/bin/env python3
"""End-to-end test for kindle/server/make_png.py (Kindle image path).

Runs the script on the sample data and reads the PNG back: the file must
be a real PNG at exactly 1072x1448 (the Kindle profile size). The script
verifies the screenshot size itself and refuses a wrong-sized shot
(quality loop D-002); png_size is also unit-checked here on a hand-built
header and on a non-PNG file. The script under test runs with CHROME_BIN
unset so the suite exercises the shipped browser discovery.
"""
import importlib.util, os, struct, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "kindle" / "server" / "make_png.py"

results = []
def check(name, cond, detail=""): results.append((name, bool(cond), detail))

spec = importlib.util.spec_from_file_location("make_png", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

check("a Chromium binary is available", mod.find_chrome() is not None,
      "set CHROME_BIN or install Chromium")

with tempfile.TemporaryDirectory() as td:
    fake = Path(td) / "fake.png"
    fake.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
                     + struct.pack(">II", 640, 480) + b"\x00" * 16)
    check("png_size reads a hand-built IHDR", mod.png_size(str(fake)) == (640, 480))
    notpng = Path(td) / "not.png"
    notpng.write_bytes(b"this is not a png file at all........")
    check("png_size returns None for a non-PNG file", mod.png_size(str(notpng)) is None)

    out = Path(td) / "briefing.png"
    env = dict(os.environ)
    env.pop("CHROME_BIN", None)
    r = subprocess.run([sys.executable, str(SCRIPT), "--out", str(out)],
                       capture_output=True, text=True, env=env)
    check("make_png exits 0 on the sample data", r.returncode == 0,
          (r.stdout + r.stderr).strip()[-300:])
    check("the PNG file is written", out.is_file())
    if out.is_file():
        check("the PNG is exactly 1072x1448", mod.png_size(str(out)) == (1072, 1448),
              str(mod.png_size(str(out))))
        check("the PNG is a real briefing, not a flat frame", out.stat().st_size > 5000,
              f"{out.stat().st_size} bytes")

passed = sum(1 for _, ok, _ in results if ok)
fails = [(n, d) for n, ok, d in results if not ok]
print(f"\nkindle_png: {passed}/{len(results)} checks passed")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}" + (f"   [{d}]" if (not ok and d) else ""))
sys.exit(1 if fails else 0)
