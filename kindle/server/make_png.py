#!/usr/bin/env python3
"""Render the ifthe morning briefing as a PNG for an e-ink panel.

Runs briefing/render_briefing.py with the kindle profile, then screenshots
the HTML with a headless Chromium at the panel's exact size. The device
fetches this PNG; it never renders HTML itself.

Usage:
    python3 make_png.py [--data DIR] [--out briefing.png]
                        [--width 1072] [--height 1448]

The browser binary is found from $CHROME_BIN, then google-chrome,
chromium, chromium-browser, chrome on PATH. Any Chromium build works;
the page is one static HTML file with no scripts or external assets.
"""
import argparse, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RENDERER = os.path.join(HERE, "..", "..", "briefing", "render_briefing.py")


def find_chrome():
    env = os.environ.get("CHROME_BIN")
    if env:
        return env
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "..", "..", "briefing", "sample-data"))
    ap.add_argument("--out", default="briefing.png")
    ap.add_argument("--width", type=int, default=1072)
    ap.add_argument("--height", type=int, default=1448)
    args = ap.parse_args()

    chrome = find_chrome()
    if not chrome:
        print("no Chromium binary found; set CHROME_BIN", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        html = os.path.join(tmp, "briefing.html")
        r = subprocess.run([sys.executable, RENDERER, "--data", args.data,
                            "--profile", "kindle", "--out", html])
        if r.returncode != 0:
            return r.returncode
        out = os.path.abspath(args.out)
        r = subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu",
                            "--hide-scrollbars", "--window-size=%d,%d" % (args.width, args.height),
                            "--screenshot=" + out, "file://" + html])
        if r.returncode != 0:
            return r.returncode
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
