#!/bin/sh
# ifthe-screensaver: fetch the morning briefing PNG and install it as the
# Kindle sleep screen image. This is the screensaver redirect shape, the
# alternative to ifthe-display.sh in the same package.
#
# Runs on a jailbroken Kindle with KUAL v2 or later. It needs no FBInk and
# sets no screensaver hold: the briefing becomes the stock sleep screen.
# The fetched PNG is saved as bg_ss00.png, the name the sleep screen
# cycles, in a folder of our own, and a one-time link step points the
# system screensaver directory at that folder (the shape the
# daily-kindle-screensaver project uses). The device sleeps normally
# between fetches, and a failed fetch costs nothing: the last installed
# image stays in place.
#
# The system screensaver directory is never guessed. Its path differs by
# firmware and the evidence this package is built from does not name it,
# so link and unlink require IFTHE_SS_DIR, set from your jailbreak's own
# documentation. link keeps the original folder as a backup next to the
# symlink and unlink restores it.
#
# The loop fetches at fixed daily times rather than on an interval. If
# the device slept through a listed time, the loop fetches at the next
# wake instead. It does not schedule a wake itself.
#
# Usage:
#   ifthe-screensaver.sh once    fetch and install a single frame
#   ifthe-screensaver.sh link    point the system screensaver dir here (one time)
#   ifthe-screensaver.sh unlink  restore the original screensaver dir
#   ifthe-screensaver.sh start   run the timed fetch loop in the background
#   ifthe-screensaver.sh stop    stop the loop
#
# Configuration (environment or edit below):
#   IFTHE_URL       full URL of briefing.png on the home server
#   IFTHE_TIMES     daily fetch times, HH:MM list (default 06:00 08:00 10:00)
#   IFTHE_SS_DIR    system screensaver directory (required for link/unlink)

IFTHE_URL="${IFTHE_URL:-http://home.local:8086/briefing.png}"
IFTHE_TIMES="${IFTHE_TIMES:-06:00 08:00 10:00}"
IFTHE_SS_DIR="${IFTHE_SS_DIR:-}"
WORK=/mnt/us/ifthe-screensaver
TMP="$WORK/briefing.tmp.png"
PNG="$WORK/bg_ss00.png"
PIDFILE=/tmp/ifthe-screensaver.pid
LOG="$WORK/ifthe-screensaver.log"
BACKUP="$IFTHE_SS_DIR.ifthe-backup"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

fetch_and_install() {
    mkdir -p "$WORK"
    if wget -q -O "$TMP" "$IFTHE_URL" && [ -s "$TMP" ]; then
        mv "$TMP" "$PNG"
        log "installed $IFTHE_URL as bg_ss00.png"
    else
        log "fetch failed, keeping last installed image"
        return 1
    fi
}

require_ss_dir() {
    if [ -z "$IFTHE_SS_DIR" ]; then
        echo "IFTHE_SS_DIR is not set: the system screensaver directory differs by firmware." >&2
        echo "Set IFTHE_SS_DIR to the path named in your jailbreak documentation and re-run." >&2
        return 1
    fi
}

link_ss() {
    require_ss_dir || exit 1
    mkdir -p "$WORK"
    if [ -L "$IFTHE_SS_DIR" ]; then
        if [ "$(readlink "$IFTHE_SS_DIR")" = "$WORK" ]; then
            echo "already linked"; return 0
        fi
        echo "$IFTHE_SS_DIR is already a symlink to $(readlink "$IFTHE_SS_DIR"); not touching it" >&2
        exit 1
    fi
    if [ ! -d "$IFTHE_SS_DIR" ]; then
        echo "$IFTHE_SS_DIR is not a directory; check IFTHE_SS_DIR against your jailbreak documentation" >&2
        exit 1
    fi
    if [ -e "$BACKUP" ]; then
        echo "backup $BACKUP already exists; resolve it before linking" >&2
        exit 1
    fi
    mv "$IFTHE_SS_DIR" "$BACKUP" || { echo "could not move $IFTHE_SS_DIR aside" >&2; exit 1; }
    if ln -s "$WORK" "$IFTHE_SS_DIR"; then
        log "linked $IFTHE_SS_DIR to $WORK (original kept at $BACKUP)"
        echo "linked"
    else
        mv "$BACKUP" "$IFTHE_SS_DIR"
        echo "symlink failed; original screensaver directory restored" >&2
        exit 1
    fi
}

unlink_ss() {
    require_ss_dir || exit 1
    if [ -L "$IFTHE_SS_DIR" ] && [ -d "$BACKUP" ]; then
        rm "$IFTHE_SS_DIR" && mv "$BACKUP" "$IFTHE_SS_DIR"
        log "unlinked $IFTHE_SS_DIR, original restored"
        echo "unlinked"
    else
        echo "$IFTHE_SS_DIR is not an ifthe link with a backup at $BACKUP; not touching it" >&2
        exit 1
    fi
}

loop() {
    echo $$ > "$PIDFILE"
    trap 'rm -f "$PIDFILE"; exit 0' TERM INT
    DONE=""
    while true; do
        DAY="$(date '+%Y-%m-%d')"
        HM="$(date '+%H:%M')"
        DUE=""
        for t in $IFTHE_TIMES; do
            if [ "$HM" = "$t" ] || [ "$HM" \> "$t" ]; then
                case " $DONE " in
                    *" $DAY@$t "*) ;;
                    *) DUE="$t" ;;
                esac
            fi
        done
        NAP=30
        if [ -n "$DUE" ]; then
            if fetch_and_install; then
                for t in $IFTHE_TIMES; do
                    if [ "$DUE" = "$t" ] || [ "$DUE" \> "$t" ]; then
                        DONE="$DONE $DAY@$t"
                    fi
                done
            else
                NAP=300
            fi
        fi
        sleep "$NAP" &
        wait $!
    done
}

case "$1" in
    once)
        mkdir -p "$WORK"; fetch_and_install ;;
    link)
        link_ss ;;
    unlink)
        unlink_ss ;;
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
        echo "stopped" ;;
    *)
        echo "usage: $0 once|link|unlink|start|stop" >&2; exit 2 ;;
esac
