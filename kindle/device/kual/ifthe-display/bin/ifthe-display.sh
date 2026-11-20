#!/bin/sh
# ifthe-display: fetch the morning briefing PNG and draw it on the Kindle.
#
# Runs on a jailbroken Kindle. Needs FBInk (bundled with most NiLuJe
# packages; this script also probes /mnt/us/libkh/bin/fbink).
# The panel holds the last frame on its own, so a failed fetch costs
# nothing: the previous briefing stays on screen.
#
# Usage:
#   ifthe-display.sh once    fetch and draw a single frame
#   ifthe-display.sh start   run the refresh loop in the background
#   ifthe-display.sh stop    stop the loop, release the screensaver hold
#
# Configuration (environment or edit below):
#   IFTHE_URL       full URL of briefing.png on the home server (required)
#   IFTHE_INTERVAL  seconds between fetches in loop mode (default 900)
#   FBINK_BIN       path to the fbink binary (default: probe)

IFTHE_URL="${IFTHE_URL:-http://home.local:8086/briefing.png}"
IFTHE_INTERVAL="${IFTHE_INTERVAL:-900}"
WORK=/mnt/us/ifthe-display
TMP="$WORK/briefing.tmp.png"
PNG="$WORK/briefing.png"
PIDFILE=/tmp/ifthe-display.pid
LOG="$WORK/ifthe-display.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

find_fbink() {
    if [ -n "$FBINK_BIN" ] && [ -x "$FBINK_BIN" ]; then echo "$FBINK_BIN"; return; fi
    for c in fbink /mnt/us/libkh/bin/fbink /mnt/us/extensions/fbink/fbink; do
        if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then echo "$c"; return; fi
    done
    echo ""
}

hold_screensaver() {
    # Keep the stock sleep screen from replacing the briefing.
    if command -v lipc >/dev/null 2>&1; then
        lipc set-prop com.lab126.powerd preventScreenSaver "$1" 2>/dev/null
    fi
}

fetch_and_draw() {
    FBINK=$(find_fbink)
    if [ -z "$FBINK" ]; then log "fbink not found"; return 1; fi
    mkdir -p "$WORK"
    if wget -q -O "$TMP" "$IFTHE_URL" && [ -s "$TMP" ]; then
        mv "$TMP" "$PNG"
        "$FBINK" --image "file=$PNG"
        log "drew $IFTHE_URL"
    else
        log "fetch failed, keeping last frame"
        return 1
    fi
}

loop() {
    echo $$ > "$PIDFILE"
    hold_screensaver 1
    trap 'hold_screensaver 0; rm -f "$PIDFILE"; exit 0' TERM INT
    while true; do
        fetch_and_draw
        sleep "$IFTHE_INTERVAL" &
        wait $!
    done
}

case "$1" in
    once)
        mkdir -p "$WORK"; fetch_and_draw ;;
    start)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            echo "already running"; exit 0
        fi
        mkdir -p "$WORK"
        nohup "$0" loop >>"$LOG" 2>&1 &
        echo "started" ;;
    loop)
        loop ;;
    stop)
        if [ -f "$PIDFILE" ]; then kill "$(cat "$PIDFILE")" 2>/dev/null; fi
        hold_screensaver 0
        echo "stopped" ;;
    *)
        echo "usage: $0 once|start|stop" >&2; exit 2 ;;
esac
