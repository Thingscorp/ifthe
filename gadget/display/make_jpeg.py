#!/usr/bin/env python3
"""Render the ifthe morning briefing as a JPEG for a Muse Gadget display board.

Runs briefing/render_briefing.py with the panel profile (800x480), then
screenshots the HTML with a headless Chromium at exactly 800x480 and
converts the shot to JPEG. The board never renders HTML itself; Muse
pushes this file to it with display.draw_url or display.draw_file.

JPEG is not a preference, it is the only format the board takes: the
Gadget SDK's image path (esp32/main/image_fetch.c) decodes JPEG and has
no PNG handling. The Kindle path keeps its PNG; this script is the
parallel output for full-UI boards such as the Elecrow CrowPanel
Advance 4.3, whose canvas is exactly 800x480.

Usage:
    python3 make_jpeg.py [--data DIR] [--out briefing.jpg]
                         [--quality 85]

The browser binary is found exactly the way kindle/server/make_png.py
finds it: that module's find_chrome() is imported and reused here, so
the two image paths can never drift apart on browser discovery.
"""
import argparse, importlib.util, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..")
RENDERER = os.path.join(REPO, "briefing", "render_briefing.py")
MAKE_PNG = os.path.join(REPO, "kindle", "server", "make_png.py")

PANEL_W, PANEL_H = 800, 480


def load_find_chrome():
    spec = importlib.util.spec_from_file_location("make_png", MAKE_PNG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.find_chrome


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(REPO, "briefing", "sample-data"))
    ap.add_argument("--out", default="briefing.jpg")
    ap.add_argument("--quality", type=int, default=85)
    args = ap.parse_args()

    find_chrome = load_find_chrome()
    chrome = find_chrome()
    if not chrome:
        print("no Chromium binary found; set CHROME_BIN", file=sys.stderr)
        return 1

    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required to write the JPEG: pip install Pillow", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        html = os.path.join(tmp, "briefing.html")
        r = subprocess.run([sys.executable, RENDERER, "--data", args.data,
                            "--profile", "panel", "--out", html])
        if r.returncode != 0:
            return r.returncode
        shot = os.path.join(tmp, "briefing.png")
        r = subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu",
                            "--hide-scrollbars",
                            "--window-size=%d,%d" % (PANEL_W, PANEL_H),
                            "--screenshot=" + shot, "file://" + html])
        if r.returncode != 0:
            return r.returncode
        out = os.path.abspath(args.out)
        img = Image.open(shot)
        if img.size != (PANEL_W, PANEL_H):
            print("screenshot is %s, expected (%d, %d)" % (img.size, PANEL_W, PANEL_H),
                  file=sys.stderr)
            return 1
        img.convert("RGB").save(out, "JPEG", quality=args.quality)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
