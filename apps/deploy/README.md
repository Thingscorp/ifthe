# ifthe: Deploy Configs

Ready-to-run Docker Compose for the next bricks of the ifthe suite, sized
for a single always-on Mac mini ("your home server") on the home network. **Actual Budget is
already running on `:5006`**. These files add everything around it.

Three stacks, brought up independently in order:

| File | Stack | Services |
|---|---|---|
| `docker-compose.foundation.yml` | Safety & reliability (do first) | Vaultwarden, AdGuard Home, Uptime Kuma |
| `docker-compose.docs.yml` | Documents & benefits | Paperless-ngx (+postgres, redis, gotenberg, tika), Stirling PDF |
| `docker-compose.family.yml` | Everyday family ops | Nextcloud (+MariaDB, redis), Wallos, Mealie, Homebox |
| `docker-compose.ai.yml` | Read-only AI exporters (optional) | actual-export, email-ingester |
| `docker-compose.dashboard.yml` | App index + ambient sleep screen | Glance, front door (Caddy), agenda-export |

Everything is **read-only toward your money**. None of these services can touch a
bank or move funds. All data stays on your home server's local disk and on your LAN/tailnet.

---

## Prerequisites

- Docker Engine + Docker Compose v2 (`docker compose version` should work).
- A `DATA_ROOT` folder on your home server's **local disk**, never an SMB/NFS share.

## Quick start

```bash
cd "apps/deploy"
cp .env.example .env
# edit .env: set DATA_ROOT, TZ, and fill in every blank secret
#   generate secrets with:  openssl rand -base64 48

bash deploy.sh            # creates the tree + ifthe_net, brings up all 3 stacks
# bash deploy.sh --with-ai   # also builds + starts the read-only AI exporters
```

`deploy.sh` is idempotent, safe to re-run. To drive the stacks by hand instead:

```bash
set -a && source .env && set +a
bash 00-create-dirs.sh
docker compose -f docker-compose.foundation.yml up -d
docker compose -f docker-compose.docs.yml up -d
docker compose -f docker-compose.family.yml up -d
```

For day-two operations (first deploy, image updates, backup/restore, health checks, and troubleshooting), see [`OPERATIONS.md`](OPERATIONS.md).

## Where to reach things (LAN)

| Service | URL | Notes |
|---|---|---|
| Actual (already up) | `https://home.local:5006` | existing |
| Vaultwarden | `https://…` (see HTTPS note) | HTTP `:8222` bound to **localhost only**; reach over HTTPS via Tailscale Serve |
| AdGuard setup wizard | `http://home.local:3000` | one-time; choose web=80, DNS=53 |
| AdGuard admin | `http://home.local:8083` | after setup |
| Uptime Kuma | `http://home.local:3001` | |
| Paperless-ngx | `http://home.local:8000` | |
| Stirling PDF | `http://home.local:8090` | |
| Nextcloud | `http://home.local:8081` | install Calendar/Tasks/Contacts/Memories in-app |
| Wallos | `http://home.local:8282` | |
| Mealie | `http://home.local:9925` | |
| Homebox | `http://home.local:7745` | set `HOMEBOX_ALLOW_REGISTRATION=false` in `.env`, then `up -d`, after first user |
| Glance (app index) | `http://home.local:8085` | service health + bookmarks |
| Front door / sleep screen | `http://home.local:8086` | LAN launcher; idles to a read-only bento ambient screen |

---

## Runtime: Colima on your home server (this matters)

your home server runs **Colima**, not Docker Desktop. The compose files are identical either way, but a
few host-side things differ (see `colima.example.yaml`):

- **`DATA_ROOT` must be on a Colima-mounted path.** Colima mounts `$HOME` writable by default
  but **not** `/Users/Shared`. Either put `DATA_ROOT` under your home (e.g.
  `/Users/you/ifthe`, works immediately) **or** add a `/Users/Shared` mount
  (`colima start --edit`, or `--mount /Users/Shared:w`). If `DATA_ROOT` isn't mounted, bind
  mounts come up **empty inside the containers**, a silent break. (Docker Desktop: use
  `/Users/Shared/ifthe` + *Settings → Resources → File sharing*. Linux: `/srv/ifthe`.)
- **Mount speed**: start Colima with `--vm-type vz --mount-type virtiofs`: best performance
  for Nextcloud/Paperless' many small files. `mountType` is immutable after first start
  (`colima delete` + recreate to change it).
- **Reaching the existing Actual**: from inside a container `host.docker.internal` resolves to
  the host under Colima (fallback `home.local`); that's how the read-only AI exporter reads
  Actual on `:5006`.
- **Port 53 (AdGuard DNS)**: on macOS it's normally free for Colima to bind. On Linux,
  `systemd-resolved` usually holds it; free it (`DNSStubListener=no`, relink
  `/etc/resolv.conf`) or map a different host port.
- **Run on boot**: `restart: unless-stopped` handles *container* restarts, but Colima itself
  must start at login; install a LaunchAgent running `colima start` (see OPERATIONS.md) and
  set the Mac to restart after power loss (System Settings → Energy).

## Why databases use named volumes but everything else uses bind mounts

This is deliberate, and it directly serves your "the AI must read the files / I must
be able to back them up" requirement:

- **Bind mounts** (under `DATA_ROOT`) for anything you or the AI need to read or
  back up as files: Paperless documents, Nextcloud **user data** (`nextcloud/data`),
  Wallos/Mealie/Homebox data, Vaultwarden's `data` dir, the Paperless `consume`
  dropbox the email ingester writes to.
- **Named volumes** for raw database *engines* (Paperless' Postgres, Nextcloud's
  MariaDB, the Redis caches). DB engines misbehave on bind mounts, especially on
  macOS' virtualized filesystem, and you should **never** back a database up by
  copying its live files anyway. You dump them instead (below).
- **Named volume for Nextcloud's code dir** (`/var/www/html`): the app tree has tens
  of thousands of small PHP files, which are slow on macOS' virtualized bind-mount FS
  and cause sluggish requests / `occ` runs. It lives on the `nextcloud_html` named
  volume (fast, local disk), while `NEXTCLOUD_DATA_DIR=/var/www/html/data` keeps your
  actual files on the `nextcloud/data` bind mount so they stay readable and backup-able.
  Nextcloud's `config.php` and installed apps live in the named volume; capture them
  with `occ config:list` / the App Store list rather than by copying files.

Named volumes still live on local disk inside Docker, this is **not** a network
share, so it stays consistent with the "no SQLite/DB over SMB" rule.

---

## Networking & remote access

- All web UIs join a shared Docker network `ifthe_net` so Uptime Kuma can monitor
  them by container name (e.g. monitor `http://paperless:8000`, `http://nextcloud:80`).
  Monitor **Actual** by its LAN URL `https://home.local:5006` since it's outside
  these files.
- **Do not port-forward any of this to the internet.** For access away from home,
  use **Tailscale** and reach services at `http://your-box.your-tailnet.ts.net:<port>`.

### Vaultwarden needs HTTPS (important)

Bitwarden's browser extensions and mobile apps **refuse to connect to a non-HTTPS
server**, and even the web vault's crypto needs a secure context; so plain
`http://home.local:8222` only really works from `localhost`. The simplest fix on
this stack is Tailscale Serve, which gives you a real cert:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:8222
```

Then set `VW_DOMAIN=https://your-box.your-tailnet.ts.net` in `.env`, and flip
`SIGNUPS_ALLOWED=true` (it's an `.env` var) just long enough to create your
accounts before setting it back to `false` and re-running `up -d`.

---

## Backups (3-2-1)

**Bind-mounted data** (the bulk of it): snapshot with restic to an encrypted
external drive, then an offsite copy:

```bash
restic -r /Volumes/Backup/ifthe backup "$DATA_ROOT" \
  --exclude "$DATA_ROOT/**/cache"
```

This captures Nextcloud's **user files** (`$DATA_ROOT/nextcloud/data`). Nextcloud's
code and `config.php` live on the `nextcloud_html` named volume, re-derivable on
reinstall, so save `docker exec nextcloud nextcloud occ config:list system` alongside
the dumps below rather than backing the volume up file-by-file.

**Databases**: take logical dumps first (don't copy live DB files):

```bash
# Paperless (Postgres)
docker exec paperless-db pg_dump -U paperless paperless > "$DATA_ROOT/paperless/export/pg-$(date +%F).sql"

# Nextcloud (MariaDB): turn on maintenance mode around big backups
docker exec nextcloud nextcloud occ maintenance:mode --on
docker exec nextcloud-db sh -c 'mariadb-dump -u root -p"$MARIADB_ROOT_PASSWORD" nextcloud' > "$DATA_ROOT/nextcloud/db-$(date +%F).sql"
docker exec nextcloud nextcloud occ maintenance:mode --off
```

**Actual**: use its in-app *Settings → Export* for a clean budget backup.
Keep the **restic repository password and the Vaultwarden admin token** somewhere
outside this system (printed/sealed); if you lose them, the backups and admin page
are unrecoverable.

---

## ⚠️ Pin versions before this becomes a real appliance

The image **names** here are all current/correct (Stirling moved from
`frooodle/s-pdf` → `stirlingtools/stirling-pdf`; Homebox moved from
`hay-kot/homebox` → `sysadminsmedia/homebox`; `bellamy/wallos` is the community
image for `ellite/Wallos`). The risk is the floating `:latest` tags, not the names.

For a box your family depends on, **pin versions** so an unattended `pull` can't
break the house:

- **Never let Paperless-ngx or Nextcloud float.** Their upgrades are
  migration-gated, skipping a major version can block startup or corrupt the DB.
  Bump them deliberately, one major at a time, after reading the release notes.
  `nextcloud:stable-apache` is a safe rolling channel; pin Paperless to a concrete
  `:2.x.y`.
- Pin the rest to at least a major: `vaultwarden/server`, `stirlingtools/stirling-pdf`,
  `bellamy/wallos`, `ghcr.io/mealie-recipes/mealie` (docs recommend a `v3.x` tag over
  `latest`), `ghcr.io/sysadminsmedia/homebox`.
- Already pinned and fine: postgres `16-alpine`, redis `7-alpine`, mariadb `11`,
  gotenberg `8`, uptime-kuma `1`.

---

## Costs & credentials

**Costs:** every service here is $0 software. The only spend in the whole suite is
SimpleFIN (~$15/yr, configured inside Actual) plus optional backup drives.

**Secrets that live in `.env` (local only, git-ignored):** Vaultwarden admin token,
Paperless DB password + secret key + admin password, Nextcloud DB passwords + admin
password, and, if you run the optional AI stack, the Actual **server** password.
No bank or SimpleFIN credentials touch these files. **Gmail** credentials live in the
ingester's `getmailrc` (under `EMAIL_CONFIG_DIR`), never in `.env`.

**External connections:** none required by these services beyond pulling images and
AdGuard's upstream DNS. SimpleFIN talks only to Actual.

---

## The custom glue (AI stack)

The two bespoke scripts now ship as their own containers in
`docker-compose.ai.yml`, wired into the same `DATA_ROOT` and `ifthe_net`:

1. **`actual-export`**: `@actual-app/api` → `$DATA_ROOT/ai/ledger.json` on a daily
   loop. Reads the host's Actual server; calls only read methods.
2. **`email-ingester`**: getmail6 fetch → `parse_emails.py` → bills/receipts JSON at
   `$DATA_ROOT/ai/parsed_emails.json`, dropping PDFs into Paperless' `consume/` for OCR,
   on a 30-minute loop. Runs getmail with `delete=false`.

Both are **strictly read-only** and verified by `scripts/guard-readonly.sh`. Start
them with `bash deploy.sh --with-ai` (or `docker compose -f docker-compose.ai.yml up
-d --build`). See `scripts/actual-export/README.md` and
`scripts/email-ingester/README.md` for the per-script env and the getmailrc the
container expects.
