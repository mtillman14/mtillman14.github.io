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

<div class="notice--danger" markdown="1">
**Before you wipe anything: make sure you can actually restore it**

A full backup is only useful if you can open it *after* the disk is gone. Before wiping a disk, converting a RAID array, or reinstalling a machine, check every item on this list. Do it after the final backup has finished, and before the first destructive command.

1. **Save every restore secret somewhere other than the machine or NAS you're about to wipe.** restic repositories are encrypted; without the password, the backup is unreadable. For my setup, that's:
   - the Linux machine's restic password (`sudo cat /etc/restic-password`) and its NAS login (`/root/.nascreds`);
   - the restic password of each Backrest repository (the daily one and the full migration one);
   - each Backblaze bucket's name, region and application key (keyID and applicationKey).

   My password manager (Vaultwarden) runs *on the NAS*, so I keep a second copy of these somewhere off the NAS as well. A password manager that lives on the disk you're wiping doesn't count.
2. **Prove the secrets work without the machine being wiped.** From a *different* machine, using only the saved copies, list the repository's snapshots (see [Restoring without the NAS](#restoring-without-the-nas)). If that fails, stop.
3. **Stop all Docker containers, *then* re-run the full backup, and only *then* wipe.** Stop every container except the backup tool itself (Backrest runs in Docker, so it has to keep running to do the backup) — Watchtower and Immich included — then run the full backup one last time. Any app still running could write data after the backup reads it, and that data would be lost in the wipe; databases copied while they're being written to can also come back broken. Don't restart anything between this backup and the wipe. See [Doing the migration](#doing-the-migration) for the commands.
4. **Check the final backup finished cleanly:** no errors, no "partial backup" warnings.
5. **Do a controlled test restore** of regular files *and* of a database dump, and check them (see [Verifying a backup with a controlled restore](#verifying-a-backup-with-a-controlled-restore)).
6. **Write down the versions you'll need to restore onto,** especially for databases (for example, Immich's version and its Postgres major version, which are in its dump filenames).

Only when every item is checked: wipe.
</div>

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

The NAS backs itself up to Backblaze B2 with [Backrest](https://github.com/garethgeorge/backrest), a web UI and scheduler for restic, running in Docker on the NAS. Backrest mounts the whole NAS volume (`/volume1`) into the container at `/userdata`, so every path below starts with `/userdata`.

I use two Backrest *plans*, each writing to its own restic repository in its own B2 bucket:

| Plan | What it's for | Schedule | Repository |
|---|---|---|---|
| **Daily** | Everything I'd be upset to lose: documents, photos, app data, the computers' restic repositories | Every night at 03:00 | Daily bucket, kept long-term |
| **Full migration** | Everything, including bulk media, as temporary storage while the NAS volume is wiped | Manual only | Separate bucket, deleted afterwards |

The split reflects what each kind of data is worth. Losing my movies and TV shows would be annoying; losing my files and photos would not be recoverable. So the daily plan sends the irreplaceable data offsite every night, and the bulk media only goes offsite when I need it to survive a wipe.

> **TODO:** NAS model, disks, and the RAID layout (RAID 1 now, converting to RAID 0).

### Backblaze B2 setup

For each repository:

1. Create a **private** bucket.
2. Set the bucket's **Lifecycle Settings** to **"Keep only the last version of the file"**. B2's default keeps every version of every file, so when restic deletes old data during a prune, B2 just hides it — and keeps billing for it. restic does its own versioning, so it doesn't need B2's.
3. Create an **application key restricted to that one bucket**. Backblaze shows the secret only once.

### Adding the repository in Backrest

- **Repository URI:** `s3:s3.<region>.backblazeb2.com/<bucket>` (restic talks to B2 through its S3-compatible API).
- **Password:** a new, long random password — this is restic's encryption password, not a Backblaze one. Generate it with `openssl rand -base64 32`.
- **Env Vars:** the bucket's application key, as restic's S3 credentials:

```text
AWS_ACCESS_KEY_ID=<keyID>
AWS_SECRET_ACCESS_KEY=<applicationKey>
```

The names say "AWS" because restic uses the same S3 protocol for every S3-compatible service.

### Run Backrest as root

My Backrest container was running as a regular user (`user: "1000:10"` in its compose file). Two problems with that:

- **It can't read everything.** The nightly logs had `permission denied` warnings for files only their owner can read: Caddy's TLS private keys and the Beszel hub's SSH key. Those files were silently missing from the backup. Docker volumes are worse — Postgres keeps its data folder readable only by its own user.
- **It can't restore ownership.** Only root can set a file's owner, so everything a non-root Backrest restores comes back owned by user 1000. Many containers need their files owned by a specific user; Postgres refuses to start if its data folder isn't owned by its own user.

Removing the `user:` line from Backrest's compose file fixed both. Check with:

{% raw %}
```bash
sudo docker inspect backrest --format 'user={{.Config.User}}'
```
{% endraw %}

which should print `user=` with nothing after it. As root, Backrest can read and write the whole NAS, so its web UI needs a login (it has one) and should only be reachable on my home network and Tailscale.

Note that recreating the Backrest container cancels any backup in progress ("Operation was incomplete when orchestrator was restarted"). That's recoverable — run the backup again and restic skips the data it already uploaded — but it has to re-read every file on disk to find out what that is.

### The daily plan

- **Paths:** `/userdata`
- **Schedule:** cron `0 3 * * *`, local time. The Linux machine's own restic backup to the NAS runs at 02:00, so each night's upload includes that night's backup.
- **Retention:** 7 daily, 4 weekly, 6 monthly snapshots.
- **Excludes**, in this order:

```text
/userdata/jellyfin/data/media/movies
/userdata/jellyfin/data/media/tv
/userdata/jellyfin/data/torrents
/userdata/time-machine
*/#recycle
/userdata/docker/immich/postgres
/userdata/@*
!/userdata/@docker
/userdata/@docker/*
!/userdata/@docker/volumes
```

Line by line:

- **Movies, TV and torrents** (about 4 TB) are replaceable, so they stay out of the daily offsite copy.
- **Time Machine** (about 2.3 TB) stays local on purpose. It's for fast, whole-machine restores of the Mac; the Mac's offsite copy is its own restic backup to the NAS, which this plan *does* include.
- **`*/#recycle`** skips every share's recycle bin.
- **Immich's live Postgres folder** is skipped because copying a running database's files can produce a broken copy. Instead, Immich dumps its database every night at 02:00 into `<library>/backups/`, inside the photo library folder, and those dumps are backed up. Immich restores from them, not from the raw folder.
- **The last four lines** skip UGOS's system folders (all named `@something`) and Docker's images and containers, but keep **`@docker/volumes`** — the data for every container that uses a Docker-managed volume. That covers apps added later automatically, without having to remember to back up each one.

The `!` lines are restic's negated patterns: a pattern starting with `!` cancels an earlier exclusion, like `.gitignore`. As with `.gitignore`, once a folder is excluded nothing inside it can be added back, which is why `@docker` has to be re-included before `@docker/*` is excluded and `@docker/volumes` re-included. Order matters.

The daily plan covers about 1.7 TB and 3.3 million files, and a typical night uploads around 0.5 GB of changes in about half an hour.

### What's in the daily backup, and what isn't

| Data | In the daily backup? |
|---|---|
| Documents, music, synced folders, other shares | Yes |
| The Linux machine's (and soon the Mac's) restic repositories | Yes |
| Immich photos and videos | Yes |
| Immich database (albums, people, faces) | Yes, via the nightly dumps |
| Docker compose files, `.env` files and bind-mounted app data under `/volume1/docker` | Yes |
| Data in Docker-managed volumes | Yes |
| Movies, TV, torrents | No — by design |
| Time Machine | No — by design |

### The full migration plan

When I need everything on the NAS to survive a wipe — in my case, converting the volume from RAID 1 to RAID 0 — a second plan backs up nearly everything to a separate bucket:

- **Paths:** `/userdata`
- **Schedule:** disabled; it only runs on **Backup Now**.
- **Retention:** keep the last 1 snapshot.
- **Excludes:**

```text
*/#recycle
/userdata/docker/immich/postgres
/userdata/time-machine
/userdata/@*
!/userdata/@docker
/userdata/@docker/*
!/userdata/@docker/volumes
```

Time Machine is excluded here too; after the wipe, the Mac just starts a fresh Time Machine backup. That leaves about 5.7 TB.

Why a separate repository in a separate bucket, rather than a second plan on the daily repository:

- **The daily backup is never at risk.** The repository holding my irreplaceable files takes no part in the migration or its clean-up.
- **Clean-up is simple.** When the migration is done, I delete the plan and the repository in Backrest, empty and delete the bucket, and delete its application key.
- **The cost:** a separate repository can't share stored data with the daily one, so the ~1.7 TB of files is uploaded a second time.

Two things I learned running it:

- **Backrest runs one operation at a time.** While the multi-day first upload runs, the daily plan's runs queue behind it ("scheduled, waiting"). That's an acceptable gap for a few days, but worth knowing.
- **Upload time is the real constraint.** 5.7 TB takes days on a home connection, and restoring it means downloading it all again. A USB drive attached to the NAS as a local Backrest repository would be much faster, if you have one big enough. I didn't.

### Doing the migration

1. Run the full plan once, with everything running, to get the bulk of the data uploaded.
2. **Right before the wipe: stop all Docker containers except Backrest, then run the full plan again.** The order is the point: stop, *then* back up, *then* wipe. Containers stopped *after* the final backup could have written data the backup never saw, and that data would be lost. Stop Watchtower first, so nothing gets updated or restarted:

{% raw %}
   ```bash
   sudo docker stop $(sudo docker ps --format '{{.Names}}' | grep -i watchtower)
   sudo docker ps --format '{{.Names}}' | grep -vx backrest | xargs -r sudo docker stop
   sudo docker ps --format '{{.Names}}'
   ```
{% endraw %}

   The last command should list only `backrest`. Then click **Backup Now** on the full plan. It only uploads what changed since the first run, so it's quick, and every database is copied while nothing is writing to it. From here until the wipe, don't start any container again — anything written after this backup won't be in it.
3. Browse that final snapshot and test-restore samples to a scratch folder: a document folder, an app's data from `@docker/volumes`, the newest Immich database dump and one movie.
4. Wipe and convert the volume, reinstall Docker and Backrest, add the full migration repository back to Backrest, and restore.
5. For Docker volumes: stop Docker, restore the whole `@docker/volumes` folder (Docker's record of which volumes exist, `metadata.db`, lives inside it), then start Docker before running `docker compose up`.
6. For Immich: restore onto the **same Immich version** the dumps were made with. The version is in the dump's filename (for example `immich-db-backup-…-v2.7.5-pg14.19.sql.gz`), so pin that version in Immich's compose file for the rebuild and update afterwards.
7. Delete the migration plan, repository and bucket.

> **TODO:** results of the migration — upload time, the test restore, and how the rebuild went.

### Restoring without the NAS

Backrest runs on the NAS, so after a wipe — or if the NAS dies — Backrest's own settings are gone too. Restoring needs, from somewhere other than the NAS:

- each repository's restic password,
- each bucket's name, region and application key.

My password manager is Vaultwarden, which *also* runs on this NAS. The Bitwarden apps keep an offline copy of the vault, but I keep a second copy of these specific secrets somewhere off the NAS as well, so a dead NAS can't lock me out of the backup of the NAS.

Any machine with restic installed can read the repositories directly, without Backrest:

```bash
export AWS_ACCESS_KEY_ID=<keyID>
export AWS_SECRET_ACCESS_KEY=<applicationKey>
restic -r s3:s3.<region>.backblazeb2.com/<bucket> snapshots
```

### Verifying a backup with a controlled restore

"The backup finished" proves the upload worked. It doesn't prove the data can be restored, or that what comes back is usable. A controlled restore — restoring samples into a scratch folder, then checking them — answers both. I do it from a machine *other than the NAS* (the Linux desktop), using only the saved secrets, which also tests [Restoring without the NAS](#restoring-without-the-nas) at the same time.

The examples use the Backblaze repository. In the snapshot, every path starts with `/userdata`, because that's where Backrest sees the NAS volume.

#### Setup

```bash
export AWS_ACCESS_KEY_ID=<keyID>
export AWS_SECRET_ACCESS_KEY=<applicationKey>
export RESTIC_REPOSITORY=s3:s3.<region>.backblazeb2.com/<bucket>
export RESTIC_PASSWORD_FILE=~/restic-test-password   # the saved copy, chmod 600
mkdir -p ~/restore-test
```

#### 1. The repository itself

```bash
restic snapshots --latest 3
restic check --read-data-subset=5%
```

`check` verifies the repository's structure and re-downloads a random 5% of the stored data to confirm it isn't damaged. It should end with `no errors were found`. (It downloads 5% of the repository, which counts against Backblaze's download allowance on a large repository.)

#### 2. Regular files

Restore a few folders that matter — a documents folder, a sample of the photo library — and have restic re-read everything it wrote, checking it against the snapshot:

```bash
restic restore latest --target ~/restore-test --verify \
  --include /userdata/<share>/<important-folder> \
  --include /userdata/docker/immich/album/library/<a-user-or-year-folder>
```

`--verify` catches anything that was restored incorrectly. To also catch anything that was *backed up* incorrectly, compare a few restored files with the originals on the NAS:

```bash
# On the test machine:
sha256sum ~/restore-test/userdata/<share>/<important-folder>/<file>
# On the NAS:
sha256sum /volume1/<share>/<important-folder>/<file>
```

The checksums should match, unless the file changed after the snapshot was taken. Then open a few of the restored files — a PDF, a photo, a video — to check they're actually usable.

#### 3. A database dump, using Immich as the example

A database backup is only good if it loads into a database. Immich writes a compressed dump of its Postgres database every night into `<library>/backups/`, so the test is: take the newest dump from the backup, load it into a throwaway Postgres, and compare it with the live database.

**Get the newest dump out of the backup.** `restic dump` writes a single file from a snapshot to standard output, with no full restore needed:

```bash
restic ls latest /userdata/docker/immich/album/backups
restic dump latest /userdata/docker/immich/album/backups/<newest>.sql.gz > ~/restore-test/immich.sql.gz
gzip -t ~/restore-test/immich.sql.gz && echo "gzip OK"
```

The filename records the Immich and Postgres versions it came from, for example `immich-db-backup-…-v2.7.5-pg14.19.sql.gz`.

**Start a throwaway Postgres from the same image Immich uses.** Immich's Postgres image includes the vector-search extensions its database needs, so a plain `postgres` image won't load the dump. Find the exact image on the NAS:

{% raw %}
```bash
sudo docker inspect immich_postgres --format '{{.Config.Image}}'
```
{% endraw %}

and start it on the test machine, with no data volume of its own to keep:

```bash
docker run -d --name immich-restore-test -e POSTGRES_PASSWORD=test <image-from-above>
until docker exec immich-restore-test pg_isready -U postgres; do sleep 2; done
```

If the extensions fail to load in the next step, copy the `command:` line from the `database` service in Immich's compose file onto the end of `docker run`.

**Load the dump.** This is [Immich's documented restore command](https://immich.app/docs/administration/backup-and-restore/), pointed at the throwaway container. The `sed` adjusts one line of the dump so Postgres can find Immich's tables:

```bash
gunzip --stdout ~/restore-test/immich.sql.gz \
  | sed "s/SELECT pg_catalog.set_config('search_path', '', false);/SELECT pg_catalog.set_config('search_path', 'public, pg_catalog', true);/g" \
  | docker exec -i immich-restore-test psql --username=postgres --dbname=postgres > ~/restore-test/immich-load.log 2>&1
grep ERROR ~/restore-test/immich-load.log
```

A few errors such as `role "postgres" already exists` are expected, because the dump recreates the database's users and the throwaway container already has one. Errors about tables, data or extensions are not.

**Compare row counts with the live database.** This query counts every row in every Immich table:

```sql
SELECT table_name,
       (xpath('/row/c/text()',
              query_to_xml(format('SELECT count(*) AS c FROM %I.%I', table_schema, table_name),
                           false, true, '')))[1]::text::bigint AS row_count
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
```

Save it as `~/restore-test/counts.sql`, then run it against the restored copy on the test machine, and against the live database on the NAS:

```bash
# Restored copy (test machine):
docker exec -i immich-restore-test psql -U postgres -d immich -At < ~/restore-test/counts.sql > restored-counts.txt
# Live database (NAS):
sudo docker exec -i immich_postgres psql -U postgres -d immich -At < counts.sql > live-counts.txt
```

Then compare the two files with `diff`. The tables that matter most — assets, albums, people, faces — should match closely. Small differences are normal: the dump is from 02:00, and the live database has changed since.

**Check the database and the photo files agree.** Pick a few random photos from the restored database and check their files exist in the restored library sample. Immich's database stores each file's path *inside the container*, so translate it to the NAS path (Immich's library folder is mounted into the container; check its compose file for where):

```bash
docker exec immich-restore-test psql -U postgres -d immich -At \
  -c 'SELECT "originalPath" FROM asset ORDER BY random() LIMIT 5;'
```

(On older Immich versions the table is called `assets` rather than `asset`.)

**Clean up:**

```bash
docker rm -f -v immich-restore-test
rm -rf ~/restore-test
```

The same pattern works for any database: take its dump out of the backup, load it into a throwaway copy of the same database software at the same version, and compare it with the live one.

### Monitoring the nightly upload

The offsite copy gets the same dead man's switch as the Linux machine's backup, with one addition: I want to know not just whether the upload *ran*, but whether it was *clean*. restic can finish a backup while skipping files it couldn't read — a "partial" backup — and the unreadable keys described above would have stayed invisible without reading the logs.

The goal:

| Backrest outcome | Healthchecks shows |
|---|---|
| Backup started | Running (Healthchecks also times the run) |
| All files backed up | **Up**, with the run's statistics |
| Finished, but some files couldn't be read | **Down**: "partial backup, N files may not have been read completely" |
| Backup or retention clean-up failed | **Down**, with restic's error |
| Never ran, or started and never finished | **Down** once the grace period runs out |

#### Backrest's hooks, and a gap in them

Backrest can run [hooks](https://github.com/garethgeorge/backrest/blob/main/docs/src/docs/hooks.md) on backup events, and has a built-in Healthchecks hook type. It picks the Healthchecks endpoint from the event: `/start` for start events, `/fail` for error events, and the plain ping URL for everything else. It also sends a text summary as the ping body, which Healthchecks shows in the check's log.

The gap: a partial backup raises `CONDITION_SNAPSHOT_WARNING`, and in Backrest's source that event isn't classed as an error. So it pings the plain URL, and **Healthchecks records a backup with unreadable files as a success.**

The workaround uses the same behaviour: for a warning, Backrest pings the URL exactly as you enter it. So a second Healthchecks hook, for warnings only, with `/fail` already on the end of its URL, turns warnings red.

One limitation: Backrest passes hooks the *number* of unreadable files, not their names. The names are in the run's log in Backrest, so the alert links there.

#### 1. The check

In Healthchecks, a new check, `NAS → Backblaze (daily)`:

- **Period:** 1 day.
- **Grace period:** 4 hours. A normal run takes about 30 minutes; the rest covers runs that wait in Backrest's queue.

#### 2. Two hooks on the daily Backrest plan

Both are the **Healthchecks** hook type, on the daily plan, with **On Error** set to ignore so a Healthchecks outage can never mark a backup as failed.

**Hook 1 — starts, successes and errors:**

- **Conditions:** `CONDITION_SNAPSHOT_START`, `CONDITION_SNAPSHOT_SUCCESS`, `CONDITION_ANY_ERROR`
- **URL:** `http://<nas-lan-ip>:8000/ping/<check-uuid>`

**Hook 2 — warnings:**

- **Condition:** `CONDITION_SNAPSHOT_WARNING`
- **URL:** `http://<nas-lan-ip>:8000/ping/<check-uuid>/fail`

`CONDITION_ANY_ERROR` rather than `CONDITION_SNAPSHOT_ERROR` means a failed retention clean-up (`forget`) is reported too, not just a failed backup.

Both hooks use this template, in place of Backrest's default, which drops the statistics whenever there's a warning:

{% raw %}
```text
{{ .EventName .Event }} — plan {{ .Plan.Id }}, {{ .FormatTime .CurTime }}
{{ if .Error }}Problem: {{ .Error }}
{{ end }}{{ if .SnapshotId }}Snapshot {{ .SnapshotId }}: {{ .SnapshotStats.TotalFilesProcessed }} files, {{ .FormatSizeBytes .SnapshotStats.TotalBytesProcessed }} processed, {{ .FormatSizeBytes .SnapshotStats.DataAdded }} new
{{ end }}Details: http://<nas-tailscale-ip>:9898
```
{% endraw %}

The hooks use the NAS's LAN address: from inside the Backrest container, that reaches Healthchecks on the same NAS without depending on Tailscale. The "Details" link uses the Tailscale address, so it opens from my phone anywhere.

#### 3. A webhook that puts Backrest's message in the alert

My Beelink webhook's message is written for the Beelink backup, so the NAS check gets its own **Webhook** integration, *Backrest alerts*. Healthchecks' `$BODY_JSON` placeholder is the body of the ping that changed the check's state, already escaped and quoted for JSON — so the phone shows exactly what Backrest reported.

**Down:** `POST http://ntfy:80/`, header `Content-Type: application/json`, body:

```json
{
  "topic": "<your-topic>",
  "title": "⚠️ $NAME",
  "message": $BODY_JSON,
  "priority": 5,
  "tags": ["warning"]
}
```

**Up:** same URL and header, body:

```json
{
  "topic": "<your-topic>",
  "title": "✅ $NAME is healthy again",
  "message": $BODY_JSON,
  "priority": 2,
  "tags": ["white_check_mark"]
}
```

#### About ntfy topics

ntfy has no list of topics to create in advance. A topic exists as soon as something publishes or subscribes to it, and the name is the only link between the two: Healthchecks publishes to a topic, the ntfy app on my phone subscribes to the same name, and if they match exactly, the message arrives. If they don't, it goes to a topic nobody is listening to and is silently lost.

Anyone who can reach the ntfy server and knows a topic's name can read and post to it — there's no login unless you turn on ntfy's access control. So I use a long random name, like a password (`openssl rand -hex 12`, plus a readable prefix). My server is only reachable on my home network and Tailscale, so it's belt and braces.

#### Testing it

The Backrest side can only be tested by a real backup run, but the Healthchecks and ntfy side can be tested by sending the check a fake warning from the NAS:

```bash
curl -fsS -d 'snapshot warning — TEST: partial backup, 6 files may not have been read completely.' \
  http://<nas-lan-ip>:8000/ping/<check-uuid>/fail
```

The phone should get "⚠️ NAS → Backblaze (daily)" with that text. Then reset the check, which should send the ✅ notification:

```bash
curl -fsS -d 'TEST reset' http://<nas-lan-ip>:8000/ping/<check-uuid>
```

#### Things that went wrong

- **The alert used the wrong webhook.** Healthchecks switches every existing integration on for a new check, so my first test arrived with the Beelink's wording. Each check's notification methods need setting by hand: *Backrest alerts* on for the NAS check only.
- **The integration's Test! button returned a 400 from ntfy.** Two mistakes in my JSON: I'd left the placeholder `<your-topic>` in place (ntfy topic names can only contain letters, numbers, `-` and `_`), and the Up body was missing a comma. ntfy rejects anything that isn't valid JSON with a 400.
- **Don't put quotes around `$BODY_JSON`.** Healthchecks includes them in the substituted value, so `"message": "$BODY_JSON"` produces `"message": """"` — invalid JSON, and another 400.
- **The Test! button has no message.** A test notification isn't caused by a real ping, so there's no body to substitute and ntfy shows its default, "triggered". The `curl` test above is the realistic one.

> **TODO:** confirm the first real run — a clean run showing the statistics in Healthchecks, and (ideally) a deliberate warning.

## Mac to NAS

> **TODO:** set up and document restic backups from the Mac to the NAS.

## Lessons

- **Monitor backups with a dead man's switch.** Without it, a broken backup looks exactly like a working one.
- **Test restores.**
- **Store the backup password somewhere other than the machine being backed up.**
- **Make backup scripts fail loudly** (`set -euo pipefail`), so a failed step can't hide behind a later successful one.
- **Turn off recycle bins on backup destinations.** Backup tools delete old data on purpose.
- **Fewer tools is better.** Three backup tools on one machine meant none of them was really looked after.
