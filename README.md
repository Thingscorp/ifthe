# ifthe

**A home server with a morning briefing.** One small always-on computer in
your home runs your household services. One screen shows the day. An AI
analyst reads the exports and briefs you, and it can never move your money.

No feeds. No scrolling. No cloud account holding your family's data. You look
at one screen in the morning, you know what today needs, you get on with it.

## The face

`apps/dashboard/frontdoor/` is a static page you leave open on a kitchen
tablet, an old monitor, or any browser on your home network:

- A launcher grid for every service, on your LAN only.
- After a few idle minutes it settles into an ambient screen: clock, date,
  a greeting, and today's agenda, exported read-only from your calendar.
- It cannot write anything. A mechanical guard in CI fails the build if the
  front door or the agenda exporter ever gains a write path.

The same briefing is built to travel: service health, whether last night's
backup ran, today's agenda, a budget snapshot, and your own tracked lists
render just as well on a small e-ink panel by the door. That is the hardware
path this project is growing toward (see Hardware below).

## What runs on the box

Four Docker Compose stacks, deployed in phases by one script
(`apps/deploy/deploy.sh`):

| Stack | Services |
| --- | --- |
| foundation | AdGuard Home (DNS filtering), Uptime Kuma (health), Vaultwarden (passwords) |
| docs | Paperless-ngx (document archive with OCR), Stirling PDF |
| family | Nextcloud (files, calendar, photos), Mealie (meals and shopping), Wallos (subscriptions), Homebox (home inventory) |
| dashboard | Glance (service index) and the front door above |

Actual Budget runs alongside as the household ledger. Bank sync is the one
paid extra in the reference home (SimpleFIN Bridge, about $15/year);
everything else here is free and open source.

Works on Linux, and on macOS via Colima (see
`apps/deploy/colima.example.yaml`). All data lives in one `DATA_ROOT` folder
on the box's own disk. Nothing is hosted anywhere else.

## The AI layer, read-only by construction

Three small exporters turn live services into plain files an assistant can
read:

- `scripts/actual-export/` writes a budget snapshot (`ledger.json`).
- `scripts/email-ingester/` parses bills and receipts from a mailbox into
  Paperless, never deleting anything server-side.
- `scripts/agenda-export/` writes today's calendar to `agenda.json` for the
  ambient screen.

On top of the exports sits a household memory (`ai/memory/`): who lives
here, what is owed, the goals, the budget rules. The analyst prompt
(`ai/SYSTEM_PROMPT.md`) binds the assistant to four hard rules: never move
money, read-only inputs only, the human performs every action, and privacy
stays home. `scripts/guard-readonly.sh` enforces the first two mechanically:
if an exporter ever gains a money-moving call, the check suite fails.

Your real memory files are gitignored. The repo ships fictional examples
only, so a stray commit cannot publish your household.

## Quick start

```bash
git clone <this repo> ifthe && cd ifthe/apps/deploy
cp .env.example .env   # fill in secrets: openssl rand -base64 48
bash deploy.sh         # preflight, directory tree, foundation + docs + family
bash deploy.sh --with-ai   # add the read-only exporters
bash ../../scripts/check.sh  # every gate green before you trust it
```

Then open the front door at `http://home.local:8086` (set your own hostname)
and leave it on a screen somewhere your household walks past.

## Hardware

The reference home runs this on an always-on Mac mini. The same stacks run
on any small Linux box, which is where this project is headed as a
[Muse Gadget](https://gadgets.muse.ai/): a Linux home box Muse can operate
(health checks, backup checks, service questions), paired with a color
e-ink morning briefing panel (a Seeed reTerminal class device) running the
front door's ambient screen. Hardware build notes land here as they are
proven, not before.

## Privacy model

- Every service is on your LAN. Remote access, if you want it, is through
  your own Tailscale tailnet, never a vendor cloud.
- The AI layer reads exported files. It has no credentials that can write,
  pay, or delete, and a CI guard keeps it that way.
- This template contains no real household data. It was extracted from a
  working private home deployment, then sanitized file by file: names,
  hostnames, paths, and the entire household memory were replaced with
  fictional examples, and internal planning files were dropped.

## Status

Working template, extracted 2026-11 from a live home deployment.
`bash scripts/check.sh` is the gate: read-only guards, syntax, compose and
config validity. `bash tests/run-tests.sh` runs the full behavioural suite
on top of it. Both pass clean on this template.
