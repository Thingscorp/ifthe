# ifthe: Operations Runbook

The day-two companion to [`README.md`](README.md). The README explains *what* the
stacks are and *why* they're shaped the way they are; this file is the *how*: the
exact commands to bring the box up, keep it patched, back it up, restore it, and
unstick it when something is wrong.

Everything here is **read-only toward your money**. None of these steps touch a
bank, SimpleFIN, or Actual. Back Actual up with its own *Settings → Export*.

Run the deploy commands from inside `apps/deploy` (where the compose files
and `.env` live). The backup/restore scripts live at the repo root under
`scripts/backup/`.

---

## Bring it over to your home server (Colima)

your home server already runs **Actual on `:5006`** and uses **Colima** as its container runtime. The
stacks here are built around that: Actual is in *none* of the compose files (the AI exporter
only reads it), so bringing this over **adds to** the box without touching what's already live.

```bash
# 1. Get the repo onto your home server (lives under ~/github with the other repos):
git clone <origin-url> ~/github/ifthe      # or: git -C ~/github/ifthe pull
cd ~/github/ifthe

# 2. Start Colima with good mount perf (see apps/deploy/colima.example.yaml):
colima start --cpu 4 --memory 8 --vm-type vz --mount-type virtiofs
#    add  --mount /Users/Shared:w  ONLY if DATA_ROOT will live under /Users/Shared

# 3. Configure + deploy:
cd "apps/deploy"
cp .env.example .env
#    set DATA_ROOT to a Colima-mounted path (e.g. /Users/you/ifthe), fill the secrets
bash deploy.sh                                          # foundation, docs, family
# bash deploy.sh --with-ai                              # + read-only exporters
docker compose -f docker-compose.dashboard.yml up -d --build   # app index + sleep screen
```

The read-only AI exporter reaches the existing Actual via
`ACTUAL_SERVER_URL=https://host.docker.internal:5006` (resolves to the host under Colima;
fall back to `https://home.local:5006`). It never manages Actual; back Actual up with its
own *Settings → Export*.

**Autostart Colima at login** (so the box self-heals after a reboot) via a LaunchAgent:

```bash
cat > ~/Library/LaunchAgents/com.ifthe.colima.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ifthe.colima</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>-lc</string><string>colima start</string></array>
  <key>RunAtLoad</key><true/>
</dict></plist>
PLIST
launchctl load ~/Library/LaunchAgents/com.ifthe.colima.plist
```

> `DATA_ROOT` must be on a path Colima mounts (it mounts `$HOME` by default, **not**
> `/Users/Shared`). If bind-mounted dirs look empty inside containers, that's the cause:
> add the mount (`colima start --edit`) and re-run. `preflight.sh` warns about this.

---

## First deploy

```bash
cd "apps/deploy"
cp .env.example .env
# edit .env: set DATA_ROOT (local disk!), TZ, and fill in EVERY blank secret.
#   generate secrets with:  openssl rand -base64 48
#   Vaultwarden admin token: docker run --rm -it vaultwarden/server /vaultwarden hash

bash deploy.sh            # preflight -> create tree + ifthe_net -> foundation, docs, family
# bash deploy.sh --with-ai   # also build + start the read-only AI exporters
```

`deploy.sh` runs `scripts/preflight.sh` for you before touching anything. Preflight
**fails** if `DATA_ROOT` is unset, if it lives under `/Volumes/*` (a mount/share;
databases must be on a local disk), or if any required secret is empty
(`VW_ADMIN_TOKEN`, `PAPERLESS_DB_PASS`, `PAPERLESS_SECRET_KEY`,
`PAPERLESS_ADMIN_PASSWORD`, `NEXTCLOUD_DB_ROOT_PASS`, `NEXTCLOUD_DB_PASS`,
`NEXTCLOUD_ADMIN_PASSWORD`). It only *warns* if Docker Compose is missing, so you can
sanity-run it before Docker is installed.

`deploy.sh` is idempotent, safe to re-run. To drive the stacks by hand instead, see
the "Quick start" block in `README.md`. After it finishes, walk the per-service
first-run setup in the README's "Where to reach things" table (AdGuard wizard,
Nextcloud apps, Homebox `HOMEBOX_ALLOW_REGISTRATION=false`, etc.).

---

## Updating images

The tags in the compose files are **pinned** on purpose (see the README's version
section). Bump them deliberately; never let an unattended `pull` decide.

**Migration-gated services: bump ONE major at a time, after reading the notes:**

- **Paperless-ngx** (`ghcr.io/paperless-ngx/paperless-ngx`, pinned `:2.x.y`) and
  **Nextcloud** (`nextcloud:NN-apache`) run migrations on startup. Skipping a major
  can block startup or corrupt the DB.
- **Before** bumping, take a fresh backup (see below) and read that project's
  release notes for the target major.
- Edit the one `image:` line in the relevant compose file, then:

  ```bash
  set -a && source .env && set +a
  docker compose -f docker-compose.docs.yml pull paperless     # or nextcloud in family.yml
  docker compose -f docker-compose.docs.yml up -d paperless
  docker logs -f paperless                                     # watch the migration finish
  ```

  Confirm it comes back healthy (next section) before moving to the next major.

**Everything else** can be bumped in the same edit-pin → `pull` → `up -d` flow, but
still one stack at a time so a bad image is easy to spot and roll back (re-pin the
old tag, `up -d` again).

---

## Backup & restore

The README documents the 3-2-1 strategy in prose; `scripts/backup/ifthe-backup.sh`
and `scripts/backup/ifthe-restore.sh` are the runnable form of exactly that. Both
no-op cleanly (exit 0 with a `SKIP:` message) if `restic`, `docker`, or a container is
absent, so they're safe to wire into cron/launchd.

**3-2-1 in one line:** keep **3** copies of the data, on **2** different media, with
**1** offsite, i.e. the live `DATA_ROOT`, a restic snapshot on an encrypted external
drive, and an offsite copy of that restic repo.

### Backup

```bash
DATA_ROOT=/Users/Shared/ifthe RESTIC_REPO=/Volumes/Backup/ifthe \
  bash scripts/backup/ifthe-backup.sh
```

What it does, in order:

1. **restic snapshot** of the bind-mounted data under `DATA_ROOT` (excludes
   `**/cache`). Initialises the repo on first run. restic reads its password from
   `RESTIC_PASSWORD` / `RESTIC_PASSWORD_FILE` exactly like the restic CLI; the
   script does not handle it.
2. **Logical DB dumps** (never copies live DB files): Paperless Postgres via
   `pg_dump` → `$DATA_ROOT/paperless/export/pg-<date>.sql`; Nextcloud MariaDB via
   `mariadb-dump` → `$DATA_ROOT/nextcloud/db-<date>.sql`, with `occ maintenance:mode`
   flipped on around the dump.

Nextcloud's code and `config.php` live on the `nextcloud_html` named volume
(re-derivable on reinstall). Capture the system config alongside the dumps with
`docker exec nextcloud nextcloud occ config:list system`. Back **Actual** up with its
in-app *Settings → Export*. Keep the **restic password** and the **Vaultwarden admin
token** somewhere outside this box (printed/sealed); lose them and the backups and
admin page are unrecoverable.

### Restore

`ifthe-restore.sh` reverses the backup in the same order. It is **destructive**:
it overwrites `RESTORE_TARGET` and DB contents, so it **dry-runs by default** and
only does real work with `DRY_RUN=0`.

```bash
# 1. dry run first: prints exactly what it WOULD do, changes nothing:
DATA_ROOT=/Users/Shared/ifthe RESTIC_REPO=/Volumes/Backup/ifthe \
  bash scripts/backup/ifthe-restore.sh

# 2. when the plan looks right, restore for real:
DATA_ROOT=/Users/Shared/ifthe RESTIC_REPO=/Volumes/Backup/ifthe \
  DRY_RUN=0 bash scripts/backup/ifthe-restore.sh
```

It restores the latest restic snapshot into `RESTORE_TARGET` (default `$DATA_ROOT`,
override to restore into a scratch dir first), then loads the **newest** `pg-*.sql` /
`db-*.sql` dump back into the running `paperless-db` / `nextcloud-db` containers
(`maintenance:mode` on around the MariaDB load). Restore **Actual** from its in-app
*Settings → Import*.

---

## Health checks

**Per-container health**: the compose files define healthchecks for the data-path
services, so `docker ps` shows `(healthy)`:

```bash
docker compose -f docker-compose.foundation.yml ps
docker compose -f docker-compose.docs.yml ps
docker compose -f docker-compose.family.yml ps
docker ps   # whole box at a glance; look for "(healthy)" / Up, not "Restarting"
```

Healthchecked: `paperless-redis`, `paperless-db` (`pg_isready`), `paperless-gotenberg`
(`curl --fail http://localhost:3000/health`), `nextcloud-db`, `nextcloud-redis`.
`paperless-tika` has **no** healthcheck on purpose; its minimal image ships neither
curl nor wget, so any probe would fail forever and block Paperless; it's left
`service_started` (don't add one).

**Uptime Kuma** (`http://home.local:3001`) is the always-on monitor. Add HTTP
monitors by container name on `ifthe_net`, e.g. `http://paperless:8000`,
`http://nextcloud:80`, `http://vaultwarden:80`, and monitor **Actual** by its LAN
URL `https://home.local:5006` since it lives outside these files.

---

## App index & ambient sleep screen

```bash
docker compose -f docker-compose.dashboard.yml up -d --build
```

Brings up three things on `ifthe_net`:

- **Glance** (`http://home.local:8085`), the app index: service health + bookmarks,
  configured in `dashboard/glance.yml`. If a service shows down but is up, the monitor
  check is running from inside the glance container where `home.local` may not resolve:
  switch that site's `url` to its container name (e.g. `http://paperless:8000`).
- **Front door / sleep screen** (`http://home.local:8086`), a static Caddy-served
  launcher (`dashboard/frontdoor/`, editable app list in `apps.json`). After 3 minutes of
  no pointer/key/touch it fades to a read-only **bento** ambient screen (clock, date,
  greeting, today's agenda); any interaction wakes it. It has **no write path**, purely a
  display surface.
- **agenda-export** (optional): read-only Nextcloud CalDAV → `$DATA_ROOT/dashboard/agenda.json`,
  which the sleep screen reads. Needs `NEXTCLOUD_CALDAV_*` in `.env`; unset → empty agenda
  ("No events today"), never an error. Never writes to the calendar.

**Kiosk / auto-display.** Point an always-on display (the Mac mini's own screen, an old
tablet, a wall panel) at `http://home.local:8086` in a fullscreen/kiosk browser. The idle
timer does the rest, no extra config. Tune the timeout via `IDLE_MS` in `frontdoor/app.js`.

**Consumer-readiness seam.** Today this is LAN-only and unauthenticated. The front door is
plain static files behind Caddy with an **OFF** `forward_auth` block in `dashboard/Caddyfile`.
When you take any of this beyond the LAN, turn that on (Authelia/Authentik on `ifthe_net`)
rather than exposing services directly. That, plus per-household tenant isolation, is the real
work between "household appliance" and "consumer product"; a sleep screen is not.

---

## Troubleshooting

**Port 53 in use (AdGuard DNS won't start, Linux).** `systemd-resolved` usually
holds port 53. Free it (`DNSStubListener=no`, relink `/etc/resolv.conf`) or map a
different host port for AdGuard. On macOS port 53 is normally free for Docker.

**Vaultwarden won't connect from the browser extension / phone.** Bitwarden clients
refuse a non-HTTPS server, so the localhost-only `:8222` HTTP port isn't enough.
Expose it over HTTPS with Tailscale Serve:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:8222
```

Then set `VW_DOMAIN=https://your-box.your-tailnet.ts.net` in `.env`, flip
`SIGNUPS_ALLOWED=true` just long enough to create accounts, set it back to `false`,
and `docker compose -f docker-compose.foundation.yml up -d` to apply.

**Nextcloud: "Access through untrusted domain."** Set `NEXTCLOUD_TRUSTED_DOMAINS` in
`.env` to the host(s) you actually use (e.g. `home.local` and your
`your-box.your-tailnet.ts.net` name), then `docker compose -f docker-compose.family.yml up -d`.
To inspect/patch live: `docker exec nextcloud nextcloud occ config:system:get trusted_domains`.

**Paperless office/email conversion failing (gotenberg unhealthy).** Probe the same
endpoint its healthcheck uses:

```bash
docker exec paperless-gotenberg curl --fail http://localhost:3000/health
```

A non-zero exit means gotenberg isn't serving on `:3000`; check
`docker logs paperless-gotenberg`. Paperless reaches it at
`http://paperless-gotenberg:3000` over `ifthe_net` and is gated on it being
`service_healthy`, so if gotenberg never goes healthy, Paperless won't start.

**General first move on any service.** `docker logs -f <container>` (names match the
`container_name:` in the compose files: `vaultwarden`, `adguard`, `uptime-kuma`,
`paperless`, `paperless-db`, `paperless-redis`, `paperless-gotenberg`, `paperless-tika`,
`stirling-pdf`, `nextcloud`, `nextcloud-db`, `nextcloud-redis`, `wallos`, `mealie`,
`homebox`).
