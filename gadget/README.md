# ifthe on the Muse Gadget (Linux Device SDK)

ifthe's gadget face: five read-only commands Muse can call on the home
box, each answering from the export files ifthe already produces. No
command opens a socket, writes a file, or moves money. The budget
command returns a bounded summary, never raw transactions, because
once the gadget is paired, what Muse reads leaves the LAN.

## Commands

| Command | Answers | Source |
|---|---|---|
| `home.services` | services up and down | status export |
| `home.backup` | last backup run and result | status export |
| `home.agenda` | today's events | agenda export |
| `home.briefing` | all of it, one call | all exports |
| `home.budget` | balances, top spend categories, income | ledger export |

Every answer carries a `stale` flag set when its source file is older
than 26 hours, so Muse can say "as of" instead of guessing.

Data locations are environment variables: `IFTHE_EXPORT_DIR` for the
briefing exports (default `/srv/ifthe/exports`), `IFTHE_LEDGER` for the
ledger (default `$IFTHE_DATA_ROOT/ai/ledger.json`, data root default
`/srv/ifthe`).

## The briefing on a display board (CrowPanel and other full-UI boards)

Full-UI display boards in the Gadget SDK, such as the Elecrow
CrowPanel Advance 4.3 (800x480), accept a pushed image from Claude.
Build the image from the same briefing data:

    python3 gadget/display/make_jpeg.py [--data DIR] [--out briefing.jpg]

It renders the panel profile and screenshots it at exactly 800x480,
the board's canvas. Muse then pushes it with `display.draw_url`
(a hosted URL) or `display.draw_file` (a path to the file on the VM).
The image shows as an overlay on the board face and clears on a tap,
a talk press, or the menu, so a morning push stays up on an untouched
panel and the next briefing is a fresh push.

The output is JPEG because the board takes nothing else: the SDK's
image path (esp32/main/image_fetch.c in the Muse Gadget SDK) decodes
JPEG and has no PNG handling at all. That was verified from the SDK
source in the project's iteration 2 check (CROWPANEL-CHECK.md,
workspace record). The Kindle path keeps its PNG; this is the parallel
output for these boards, and neither path changes the other.

## Install on the gadget box

Prerequisite: the Muse Gadget Linux service installed and paired
(SDK token from gadgets.muse.ai), running as a dedicated no-sudo
account. Do not pair a stock install under a personal account: the
SDK's built-in `system.run` gives Muse a general shell with that
account's permissions. Pair it with the SDK's command_guard policy in
front (allow `device.health` and the five `home.*` commands, confirm
or block the rest; confirm behaves as block in this protocol), per
the plan this repo was built from.

    sudo install -m 0755 gadget/bin/ifthe-home /usr/local/bin/ifthe-home
    sudo install -d -m 0755 /etc/musegadget/commands.d
    sudo install -m 0644 gadget/commands.d/*.json /etc/musegadget/commands.d/
    sudo systemctl restart musegadget

The SDK loader refuses definitions that are not root-owned and free of
group and world write access when the service runs as root, so keep
the modes above.

## Tests

    python3 gadget/tests/test_home.py

Behavior tests against fixtures, including the budget boundary:
October spend never leaks into November's summary, and no transaction
or payee data appears in the budget answer. The display JPEG path has
its own end-to-end test in the repo suite, tests/test_display_jpeg.py,
which runs make_jpeg.py on the sample data and reads the result back
with PIL (format, exact size, not a flat frame).

Validation (2026-11-20): all five definitions pass the SDK's own
commands.py loader from the muse-gadget-sdk checkout: parse, load,
check_params, and the registered spec, including the optional `month`
parameter on `home.budget` (declared in its definition; a non-string
month is rejected by the loader's own check). The loader's directory
trust check applies when the service runs as root, so the install
modes above are part of the contract. The SDK's own commands and
command_guard test files pass in the same checkout (186 passed; one
test fails only because it drops privileges and cannot execute the
sandbox's test virtualenv, an artifact of this machine, not the SDK).
