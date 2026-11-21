#!/usr/bin/env python3
"""End-to-end test for gadget/display/make_jpeg.py (CrowPanel image path).

Runs the script on the sample data, then reads the JPEG back with PIL:
format must be JPEG, size exactly 800x480 (the CrowPanel canvas and the
briefing panel profile), and the image must be a real briefing, not a
blank or flat frame. Needs a Chromium binary and Pillow; the browser is
located with the same find_chrome() the scripts ship (imported from
kindle/server/make_png.py), and the script under test runs with
CHROME_BIN unset so the suite exercises that shipped discovery instead
of an override.
"""
import importlib.util, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "gadget" / "display" / "make_jpeg.py"
DATA = ROOT / "briefing" / "sample-data"
MAKE_PNG = ROOT / "kindle" / "server" / "make_png.py"

results = []
def check(name, cond, detail=""): results.append((name, bool(cond), detail))


def shared_find_chrome():
    spec = importlib.util.spec_from_file_location("make_png", MAKE_PNG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.find_chrome()


chrome = shared_find_chrome()
check("a Chromium binary is available", chrome is not None,
      "set CHROME_BIN or install Chromium")

if chrome is not None:
    env = {k: v for k, v in os.environ.items() if k != "CHROME_BIN"}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "briefing.jpg"
        r = subprocess.run([sys.executable, str(SCRIPT), "--data", str(DATA),
                            "--out", str(out)],
                           capture_output=True, text=True, env=env, timeout=300)
        check("make_jpeg.py exits 0", r.returncode == 0,
              (r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout) else "")
        check("JPEG file was written", out.exists())
        if out.exists():
            from PIL import Image
            size_bytes = out.stat().st_size
            img = Image.open(out)
            check("format is JPEG", img.format == "JPEG", f"got {img.format}")
            check("size is exactly 800x480", img.size == (800, 480), f"got {img.size}")
            check("mode is RGB (no alpha)", img.mode == "RGB", f"got {img.mode}")
            check("file is non-trivial in size", size_bytes > 5000,
                  f"got {size_bytes} bytes")
            colors = img.getcolors(800 * 480)
            distinct = len(colors) if colors is not None else 800 * 480
            check("image is not a single flat color", distinct > 20,
                  f"got {distinct} distinct colors")

passed = sum(1 for _, ok, _ in results if ok)
fails = [(n, d) for n, ok, d in results if not ok]
print(f"\ndisplay_jpeg: {passed}/{len(results)} checks passed")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}" + (f"   [{d}]" if (not ok and d) else ""))
sys.exit(1 if fails else 0)
