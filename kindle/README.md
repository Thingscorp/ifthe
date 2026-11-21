# ifthe on a Kindle

An old Kindle as the briefing panel: the home server renders the morning
briefing as a PNG, the Kindle fetches it over the LAN and draws it on the
e-ink screen, and the panel holds the frame while the device sleeps.

Status: BUILT. The server half runs today (see the check below). The device
half is written from the documented Kindle homebrew stack, in two shapes
(direct draw and screensaver redirect, below), and has not been run on
hardware yet; it needs a jailbroken Kindle to prove.

## Server side

`server/make_png.py` renders `briefing/` with the kindle profile (portrait,
black on white, 1072x1448 for Paperwhite 3 and later) and screenshots it to
`briefing.png` with a headless Chromium:

    python3 kindle/server/make_png.py --out briefing.png

Serve the PNG on the LAN any way you like. For a first test:

    python3 -m http.server 8086 --directory /path/to/output

Run make_png.py on the same schedule as the briefing itself (a cron entry
next to the agenda exporter is the natural home), so the PNG is fresh when
the Kindle wakes.

## Device side

Needs, in order:

1. A jailbreak for your exact model and firmware. Steps differ per device;
   kindlemodding.org's wizard takes the first 8 digits of the serial number
   and names the one method that fits. Do that first, with its update
   blocking, before installing anything here.

Then pick one of the two shapes below. Both fetch the same server PNG;
they differ in how it reaches the screen.

### Shape 1: direct draw (device/ifthe-display.sh)

Needs FBInk, the framebuffer image tool every Kindle display project
uses. It comes bundled with most NiLuJe packages (KUAL/MRPI installs
included); the script probes `fbink` on PATH and
`/mnt/us/libkh/bin/fbink`.

With KUAL installed, copy `device/kual/ifthe-display/` into the Kindle's
`extensions/` folder and the script into its `bin/`:

    extensions/ifthe-display/config.xml
    extensions/ifthe-display/menu.json
    extensions/ifthe-display/bin/ifthe-display.sh

Set IFTHE_URL at the top of the script to your server's briefing.png
address. Without KUAL, copy the script anywhere on /mnt/us and run it
from a shell or a scriptlet instead.

The script has three modes: `once` draws a single frame, `start` runs the
fetch loop in the background (every 15 minutes by default), `stop` ends it.
In loop mode it sets the powerd `preventScreenSaver` flag so the stock
sleep screen does not replace the briefing, and releases the flag on stop.
A failed fetch keeps the last frame, which e-ink holds for free.

The cost: the hold means the stock sleep screen never shows, and the
loop wakes on its interval whether or not the briefing changed, so this
shape spends battery to stay current while the device is awake.

### Shape 2: screensaver redirect (device/ifthe-screensaver.sh)

Status: BUILT, not run on hardware, same as shape 1.

Instead of drawing to the framebuffer, the fetched PNG is installed as
the sleep screen image itself, the shape the daily-kindle-screensaver
project (a KUAL v2+ extension) uses. The script saves the PNG as
`bg_ss00.png`, the name the sleep screen cycles, in its own folder
(`/mnt/us/ifthe-screensaver`), and a one-time link step points the system
screensaver directory at that folder. The stock firmware then shows the
briefing exactly when the device sleeps. No FBInk, and no screensaver
hold: the briefing is the sleep screen.

Install it the same way as shape 1: with KUAL, copy
`device/kual/ifthe-screensaver/` into `extensions/`; without KUAL, copy
`device/ifthe-screensaver.sh` anywhere on /mnt/us. Set IFTHE_URL the same
way. Then, once, from a shell:

    IFTHE_SS_DIR=<screensaver directory> ifthe-screensaver.sh link

The system screensaver directory's path differs by firmware, and this
package does not guess it: take the path from your jailbreak's own
documentation for the screensaver folder. `link` refuses to run without
IFTHE_SS_DIR, keeps the original folder as `<dir>.ifthe-backup` next to
the new symlink, and `ifthe-screensaver.sh unlink` restores it.

Modes: `once` fetches and installs a single frame, `start` runs the
timed loop in the background, `stop` ends it, plus `link` and `unlink`
above. The loop fetches at fixed daily times (06:00, 08:00, 10:00 by
default, the daily-kindle-screensaver examples; set IFTHE_TIMES to
change them) instead of on an interval, because a briefing changes a
few times a day. If the device slept through a listed time, the loop
fetches at the next wake; it does not schedule a wake itself. Between
fetches the device sleeps normally. A failed fetch keeps the last
installed image and retries a few minutes later.

### How to pick

Direct draw is the default here because it needs nothing beyond FBInk:
pick it for a plugged-in panel that should stay current while awake.
Pick the screensaver redirect when the panel mostly sits asleep and
battery matters: the briefing shows at sleep, updates land a few times
a day, and the device keeps its normal sleep behavior. Its costs are the
one-time link step and a screen that only ever shows the most recent
fetch.

## Notes

- The image must arrive at panel size and orientation. FBInk does not
  rotate; the kindle profile renders at the panel's native portrait size.
- Update rhythm: a morning briefing wants a handful of fetches a day.
  Shape 1's 15 minute loop default is for testing (set IFTHE_INTERVAL, or
  call `once` from the device's own scheduler); shape 2 fetches at its
  fixed daily times by design (set IFTHE_TIMES).
- Audio: most dashboard Kindles (Paperwhite line) have no speaker. The
  panel's job is the screen; anything spoken belongs to the gadget or the
  phone.
