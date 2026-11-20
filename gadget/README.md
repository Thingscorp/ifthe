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
or payee data appears in the budget answer.

Open verification: the definitions follow the SDK's documented
drop-in format; validating them with the SDK's own commands.py loader
from a checkout is the last Slice 0 step before any pairing. The
optional `month` parameter on `home.budget` is accepted by the
program but not yet declared in its definition file, pending that
loader check.
