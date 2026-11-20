# ifthe on a Kindle

An old Kindle as the briefing panel: the home server renders the morning
briefing as a PNG, the Kindle fetches it over the LAN and draws it on the
e-ink screen, and the panel holds the frame while the device sleeps.

Status: BUILT. The server half runs today (see the check below). The device
half is written from the documented Kindle homebrew stack and has not been
run on hardware yet; it needs a jailbroken Kindle to prove.

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
2. FBInk, the framebuffer image tool every Kindle display project uses. It
   comes bundled with most NiLuJe packages (KUAL/MRPI installs included);
   `device/ifthe-display.sh` probes `fbink` on PATH and
   `/mnt/us/libkh/bin/fbink`.
3. This package. With KUAL installed, copy `device/kual/ifthe-display/`
   into the Kindle's `extensions/` folder and the script into its `bin/`:

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

## The other shape: screensaver redirect

Instead of drawing directly, the fetched PNG can be dropped where the
sleep screen reads its images (the bg_ss00.png slot, with the screensaver
directory redirected). The briefing then appears exactly when the device
sleeps, with no screensaver hold needed. Projects such as
daily-kindle-screensaver work this way. The direct-draw loop above is the
default here because it needs nothing beyond FBInk; switch shapes if your
jailbreak generation makes the redirect cleaner.

## Notes

- The image must arrive at panel size and orientation. FBInk does not
  rotate; the kindle profile renders at the panel's native portrait size.
- Update rhythm: a morning briefing wants a handful of fetches a day. The
  15 minute loop default is for testing; a few fixed times a day is the
  battery-friendly setting (set IFTHE_INTERVAL, or call `once` from the
  device's own scheduler).
- Audio: most dashboard Kindles (Paperwhite line) have no speaker. The
  panel's job is the screen; anything spoken belongs to the gadget or the
  phone.
