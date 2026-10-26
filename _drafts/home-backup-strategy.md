---
layout: single
title:  "My home backup strategy: Linux and Mac to a NAS, NAS to Backblaze"
tags:
  - documentation
  - backups
---

This post documents the backup setup I use for my home computers: how I consolidated what I had, added monitoring so failures can't go unnoticed, and tested that restores actually work. It's long, because I wanted to write down the problems I hit along the way as well as the final configuration.

The end goal is a standard [3-2-1 backup](https://www.backblaze.com/blog/the-3-2-1-backup-strategy/): three copies of my data, on two kinds of storage, with one copy offsite.

```text
Linux desktop (Ubuntu) ──restic──┐
                                 ├──> UGREEN NAS ──Backrest/restic──> Backblaze B2
Mac ─────────────────restic──────┘
```

- **Copy 1:** the original files on each computer.
- **Copy 2:** a [restic](https://restic.net) repository per computer on my NAS. Fast to restore from, on my home network.
- **Copy 3:** the NAS backs itself up — including those restic repositories — to Backblaze B2 every night, using [Backrest](https://github.com/garethgeorge/backrest) (a web UI and scheduler for restic) running in Docker.

Every backup checks in with a self-hosted [Healthchecks](https://healthchecks.io) instance, which pushes an alert to my phone through a self-hosted [ntfy](https://ntfy.sh) server if a backup fails or doesn't happen.

> **TODO:** a sentence or two on why this design — e.g. one offsite pipeline and one bill, fast local restores, everything in one place before it leaves the house.

## The hardware and software

| Piece | What it is |
|---|---|
| Linux desktop | Beelink mini PC (AMD Ryzen "Phoenix" APU), Ubuntu 24.04 |
| Mac | MacBook Pro |
| NAS | UGREEN NAS running UGOS, with Docker |
| Offsite | Backblaze B2 bucket, written by Backrest |
| Networking | Tailscale on every device |
| Container updates | Watchtower on the NAS |

> **TODO:** NAS model and disks, and anything notable about how the NAS volume and shares are set up.

## Where I started

Before this, the Linux machine had accumulated three overlapping approaches to backups:

1. **rsnapshot**, run daily by anacron, writing hard-linked snapshots of `/home` and a few system folders to a NAS share mounted over SMB. A custom pre-backup script also copied any file deleted since the last snapshot into a `removed-files-backup` folder, forever.
2. **restic**, run nightly at 02:00 by a systemd timer, to a repository on the same NAS share.
3. A custom suspend hook that replaced Ubuntu's normal suspend command with `rtcwake`, so the machine would wake itself at 01:55 for the restic backup.

Timeshift and Déjà Dup were also installed, but had never been configured to run.

On the NAS, Backrest backs up the NAS volume to Backblaze B2 every night at 03:00, skipping bulk media (movies, TV, torrents), Time Machine and recycle bins.

> **TODO:** how and when you set up the original rsnapshot and restic jobs, and the Backrest plan.

## Consolidating on restic

Two tools backing up the same machine to the same NAS is one too many, so I picked one. I kept restic:

- Its repositories are deduplicated, compressed and encrypted — important on a nearly full NAS, and the data is encrypted before it ever reaches Backblaze.
- Backrest is restic too, so there's one tool to learn.

The trade-off is that restoring this machine from Backblaze takes two steps: restore the restic repository folder with Backrest, then restore files from that repository with restic. With rsnapshot, Backblaze would hold plain files, but that didn't outweigh restic's advantages.

### Removing the old tools

```bash
sudo apt purge rsnapshot timeshift deja-dup
sudo apt autoremove --purge
dconf reset -f /org/gnome/deja-dup/
```

plus deleting the rsnapshot configs, scripts and logs, and the custom suspend hook (`/etc/systemd/system/systemd-suspend.service.d/override.conf` and its script). Removing that hook also matters for suspend reliability: it bypassed `systemd-sleep` entirely, including the hooks other software installs to run before sleep and after waking.

The wake-at-01:55 trick isn't needed anyway. The restic timer uses `Persistent=true`, so if the machine is asleep or off at 02:00, systemd runs the missed backup as soon as it wakes or boots — and if the machine was asleep, nothing changed that needed backing up.

### Waiting for the NAS at boot

Because of `Persistent=true`, a missed backup can start a few seconds into boot — before the NAS share is mounted, in which case restic finds an empty folder and fails with `unable to open config file`. The backup service now waits for the share:

```ini
# /etc/systemd/system/beelink-backup.service.d/mount.conf
[Unit]
RequiresMountsFor=/mnt/ugreen-nas
```

### The backup script

The script that `beelink-backup.service` runs. Compared to my original version:

- **`set -euo pipefail`.** The original had no error handling, so if `restic backup` failed, the script carried on to `restic forget`, and the service reported whatever *that* returned. A failed backup could look like a success.
- **More of the system is covered:** Docker volumes (with a proper database dump when the container is running), everyone's crontabs, and the signing keys for third-party apt repositories.
- **A list of manually installed packages**, which is what you actually reinstall from on a fresh install.
- **`--group-by host` on `forget`.** By default, restic applies the retention policy separately to each distinct *set of backed-up paths*. When I added paths, the old snapshots ended up in their own group that never received new snapshots, so the retention policy would have kept them forever.

{% raw %}
```bash
#!/bin/bash
# Nightly restic backup of the Beelink to the NAS.
# Install as /usr/local/bin/beelink-backup.sh (run by beelink-backup.service).

# Stop at the first failure so systemd (and Healthchecks) see it.
set -euo pipefail

REPO="/mnt/ugreen-nas/beelink-backup"
PASSWORD_FILE="/etc/restic-password"

# Restore aids, saved into a backed-up folder before each run.
EXTRAS=/root/backup-extras
mkdir -p "$EXTRAS"

# Installed packages: full selection state, plus just the ones installed by
# hand (the list to reinstall from on a fresh Ubuntu install).
dpkg --get-selections > "$EXTRAS/installed-packages.txt"
apt-mark showmanual > "$EXTRAS/manual-packages.txt"

# Consistent dump of the knowhow MySQL database, if its container is running.
# Copying a live database's files can capture a half-written state.
if docker ps --format '{{.Names}}' | grep -qx knowhow-mysql; then
    docker exec knowhow-mysql sh -c \
        'exec mysqldump --all-databases --single-transaction -uroot -p"$MYSQL_ROOT_PASSWORD"' \
        > "$EXTRAS/knowhow-mysql.sql"
fi

# Run backup
restic backup \
  /home/mtillman \
  /etc \
  /usr/local \
  /root \
  /var/spool/cron/crontabs \
  /usr/share/keyrings \
  /var/lib/docker/volumes \
  --repo "$REPO" \
  --password-file "$PASSWORD_FILE" \
  --exclude /home/mtillman/.cache \
  --exclude /home/mtillman/.local/share/Trash \
  --exclude /home/mtillman/Downloads \
  --exclude /root/.cache \
  --exclude /var/lib/docker/volumes/vscode

# Forget old snapshots per retention policy. Group by host only, so snapshots
# from before a change to the backed-up paths still expire under the policy.
restic forget \
  --repo "$REPO" \
  --password-file "$PASSWORD_FILE" \
  --group-by host \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 6 \
  --prune
```
{% endraw %}

Before changing retention settings, preview them with `--dry-run`:

```bash
sudo restic -r /mnt/ugreen-nas/beelink-backup --password-file /etc/restic-password \
  forget --group-by host --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --dry-run
```

## Monitoring: Healthchecks and ntfy, self-hosted on the NAS

**A backup that fails silently is barely better than no backup**, and from the machine's side, a broken backup looks exactly like a working one.

I used [Healthchecks](https://healthchecks.io) because it works as a *dead man's switch*. Each successful backup sends a "check-in" to Healthchecks, and if a check-in doesn't arrive on time, Healthchecks sends an alert. That catches all the ways a backup can quietly stop:

- the backup ran and failed,
- the backup never ran at all,
- the machine or NAS was off.

An alert that fires *when a job fails* can't catch the last two, because nothing runs to send it.

Healthchecks sends its alerts to [ntfy](https://ntfy.sh), which pushes them to the ntfy app on my iPhone. Both run on the NAS in one Docker Compose project.

### The Compose file

```yaml
# Self-hosted Healthchecks + ntfy for backup monitoring.
services:
  healthchecks:
    # "latest" so Watchtower picks up new releases.
    image: healthchecks/healthchecks:latest
    container_name: healthchecks
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DB: postgres
      DB_HOST: db
      DB_NAME: hc
      DB_USER: postgres
      # Allow alerts to the ntfy container, which is on a private Docker network.
      INTEGRATIONS_ALLOW_PRIVATE_IPS: "True"
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  db:
    # Pinned to the major version: Watchtower applies 17.x updates, but a jump
    # to a new major version would need a manual data upgrade.
    image: postgres:17
    container_name: healthchecks-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: hc
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - hc-db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres", "-d", "hc"]
      interval: 5s
      retries: 10
      # First start initialises the database, which takes ~30s on NAS storage;
      # failed checks during this window don't count.
      start_period: 120s

  ntfy:
    image: binwiederhier/ntfy:latest
    container_name: ntfy
    restart: unless-stopped
    command: serve
    environment:
      # NAS's Tailscale address, so the phone can subscribe at home or away.
      # Must match the server URL in the phone app exactly (iOS push relay).
      NTFY_BASE_URL: http://<nas-tailscale-ip>:8001
      NTFY_CACHE_FILE: /var/cache/ntfy/cache.db
      # Instant delivery on iPhone: ntfy.sh relays a wake-up signal only;
      # the message itself is fetched from this server.
      NTFY_UPSTREAM_BASE_URL: https://ntfy.sh
    ports:
      - "8001:80"
    volumes:
      - ntfy-cache:/var/cache/ntfy

volumes:
  hc-db:
  ntfy-cache:
```

And the `.env` next to it:

```bash
# Generate each secret with: openssl rand -hex 32
SECRET_KEY=<random>
DB_PASSWORD=<random>
DEBUG=False
SITE_ROOT=http://<nas-tailscale-ip>:8000
SITE_NAME=Backup checks
ALLOWED_HOSTS=<nas-tailscale-ip>,<nas-lan-ip>,localhost
REGISTRATION_OPEN=False
EMAIL_USE_VERIFICATION=False
```

Then:

```bash
docker compose up -d
docker exec -it healthchecks /opt/healthchecks/manage.py createsuperuser
```

### Things that went wrong setting it up

- **SQLite isn't enough.** My first attempt used Healthchecks' default SQLite database. The container ran four web workers plus background processes for alerts and reports, all writing to one SQLite file, and the alert sender kept crashing with `database is locked`. Because the container's startup script exits when any of its processes exits, the whole container went into a restart loop. Healthchecks' own settings describe SQLite as a quick-start default; its Docker example uses Postgres, and so does mine now.
- **Postgres is slow to initialise on NAS storage.** On first start, the official Postgres image creates the database with a temporary server and then restarts. On my NAS, that shutdown took 30 seconds, and the health check gave up first. `start_period` gives it a grace period.
- **Wait for migrations before `createsuperuser`.** Healthchecks applies its database migrations at every start, which takes a while on slow storage. Running `createsuperuser` before they finished failed with a confusing `null value in column "last_login"` error.
- **Watchtower and version tags.** Watchtower updates a container when the image behind its current tag changes; it never switches tags. A pinned version like `v4.4` would never update, so Healthchecks and ntfy use `latest`. Postgres is pinned to `17` so it gets 17.x updates but never an automatic major upgrade, which would leave the database unreadable.

### Getting alerts on the phone

- Install the **ntfy** app, allow notifications, set its default server to `http://<nas-tailscale-ip>:8001`, and subscribe to a long, random topic (`openssl rand -hex 12`).
- **Tailscale** on the phone means alerts arrive away from home too.
- **On iPhone, `NTFY_UPSTREAM_BASE_URL` is required for instant notifications.** Apple only allows push through ntfy's official server, so a self-hosted server forwards a wake-up signal through ntfy.sh, and the phone then fetches the message itself from my NAS. The server address in the app must match `NTFY_BASE_URL` exactly.

Healthchecks has a built-in ntfy integration, but its message format is fixed (`<check> is DOWN`). I used its **Webhook** integration instead, which lets me write the message. For "down":

- **Method and URL:** `POST http://ntfy:80/`
- **Header:** `Content-Type: application/json`
- **Body:**

```json
{
  "topic": "<your-topic>",
  "title": "⚠️ Backup missed: $NAME",
  "message": "The $NAME backup hasn't checked in on time ($NOW). Check the Beelink and the NAS.",
  "priority": 5,
  "tags": ["warning"]
}
```

The topic and title go in a JSON body rather than ntfy's `Title:` header because HTTP header values are limited to plain ASCII, so the emoji wouldn't survive.

### Checking in from the backup

Instead of editing the backup script, the check-ins are a systemd override on the backup service:

```ini
# /etc/systemd/system/beelink-backup.service.d/healthchecks.conf
[Service]
# Runs only after a successful backup. "-" keeps a failed ping from
# marking the backup itself as failed.
ExecStartPost=-/usr/bin/curl -fsS -m 10 --retry 3 -o /dev/null http://<nas-lan-ip>:8000/ping/<check-uuid>
# Runs after every attempt; reports failures right away instead of waiting
# for the check's grace period to run out.
ExecStopPost=-/bin/sh -c 'if [ "$SERVICE_RESULT" != "success" ]; then /usr/bin/curl -fsS -m 10 --retry 3 -o /dev/null http://<nas-lan-ip>:8000/ping/<check-uuid>/fail; fi'
```

The check in Healthchecks has a period of 1 day and a grace period of 2 hours. The check-in uses the NAS's LAN address, so it doesn't depend on Tailscale being up.

One limit of self-hosting: if the NAS itself goes down, Healthchecks goes down with it and can't alert me.

## Testing a restore

A backup you've never restored from is a hope, not a backup. I restored a realistic sample — documents, app and desktop settings, all of `/etc`, the restore aids and the MySQL volume — into a scratch folder:

```bash
sudo restic -r /mnt/ugreen-nas/beelink-backup --password-file /etc/restic-password \
  restore latest --target /root/restore-test \
  --include /home/mtillman/Documents --include /home/mtillman/.config \
  --include /etc --include /root/backup-extras \
  --include /var/lib/docker/volumes/knowhow-app_mysql_data
```

17 GiB came back in about six minutes. Then:

- `diff -rq` against the originals found no differing files. The only messages were about `python` symlinks inside old Python virtual environments, which were already broken on the live system and were restored exactly as they were.
- `stat` showed ownership and permissions were preserved, for both system files (`/etc/shadow`, `root:shadow 640`) and my own files.
- `restic check --read-data-subset=5%` re-read a random 5% of the stored data from the NAS and found no errors.

## If I ever have to rebuild the Linux machine

A file-level backup doesn't restore a bootable machine on its own. The plan is:

1. Install Ubuntu fresh, and install restic.
2. Get the restic password from my password manager, and the NAS login.
3. Mount the NAS share and restore `/root/backup-extras` to get the package lists.
4. Re-add the third-party apt sources and keys from the backup (`/etc/apt` and `/usr/share/keyrings`), then reinstall from `manual-packages.txt`.
5. Restore `/home/mtillman`, crontabs and Docker volumes, and selectively restore what I need from `/etc`. Restoring all of `/etc` over a fresh install isn't safe — files like `/etc/fstab` refer to disk IDs that will have changed.

The restic password is the single most important thing here. It's stored on the machine and inside the backup, but the backup is encrypted with it, so after a wipe the only copy that helps is one kept somewhere else.

## NAS to Backblaze

> **TODO:** review and document the Backrest plan and repository settings (schedule, retention, excludes, prune and check policies), and add a Healthchecks check for the nightly upload.

## Mac to NAS

> **TODO:** set up and document restic backups from the Mac to the NAS.

## Lessons

- **Monitor backups with a dead man's switch.** Without it, a broken backup looks exactly like a working one.
- **Test restores.**
- **Store the backup password somewhere other than the machine being backed up.**
- **Make backup scripts fail loudly** (`set -euo pipefail`), so a failed step can't hide behind a later successful one.
- **Turn off recycle bins on backup destinations.** Backup tools delete old data on purpose.
- **Fewer tools is better.** Three backup tools on one machine meant none of them was really looked after.
