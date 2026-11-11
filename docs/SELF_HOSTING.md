# Self-hosting

How to run the public `lite` stack on a single server: Caddy (the site and the API, with HTTPS),
the read-only API, and the daily job. Written for **Debian 13**; Ubuntu 24.04 LTS differs only
where noted.

**What it needs:** 2 vCPUs, 2 GB of RAM (the stack uses about 1.5 GB), 20 GB of disk for the first
year, and a DNS name. Nothing about your server (addresses, logins, backup locations) belongs in
this repository: keep it in your password manager or a SOPS-encrypted file.

Placeholders below: `SERVER` is the server's address, `you` your admin user, and
`ledger.example.org` your domain.

## 1. Before the first login

- Create the server with **Debian 13** and, if the provider allows it, your **SSH public key**.
- Point DNS at it: an `A` record (IPv4) and an `AAAA` record (IPv6) for your domain. Do this
  early; Caddy needs it to get the HTTPS certificate.

## 2. Admin user and SSH

Log in as the user the provider gives you (`root` or `debian`), then create your own user:

```sh
adduser you
usermod -aG sudo you
install -d -m 700 -o you -g you /home/you/.ssh
cp ~/.ssh/authorized_keys /home/you/.ssh/   # if your key was installed at creation
chown you:you /home/you/.ssh/authorized_keys
```

If no key was installed, run `ssh-copy-id you@SERVER` from your own machine instead. **Check that
`ssh you@SERVER` and `sudo -v` work in a second terminal before going on.**

Then allow keys only, and no root login:

```sh
sudo tee /etc/ssh/sshd_config.d/10-hardening.conf >/dev/null <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
sudo sshd -t && sudo systemctl reload ssh
```

## 3. Updates

```sh
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y unattended-upgrades git make rsync   # rsync: for pulling backups
sudo dpkg-reconfigure -plow unattended-upgrades   # answer Yes (Ubuntu has this on already)
```

Security updates now install daily. Kernel updates take effect after a reboot; check now and
then with `ls /var/run/reboot-required`.

## 4. Firewall

```sh
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
```

**Docker bypasses ufw for published ports.** That is why the stack publishes only 80 and 443
(Caddy); the API and the job are reachable only inside Docker's network. Don't add `ports:` to
other services. Your provider's network firewall, if it has one, is a useful second layer.

## 5. Docker

Install Docker Engine from Docker's own repository (Debian's `docker.io` package lags behind):

```sh
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

On Ubuntu, replace both `debian` in the URLs with `ubuntu`. Rotate container logs so they can't
fill the disk:

```sh
echo '{ "log-driver": "local" }' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```

Add yourself to the `docker` group (`sudo usermod -aG docker you`, then log in again). Membership
is equivalent to root, so give it only to admins.

## 6. Deploy

```sh
sudo install -d -o you -g you /srv/compromise-ledger
git clone https://github.com/csp4z/compromise-ledger.git /srv/compromise-ledger/app
cd /srv/compromise-ledger/app
# The job (UID 10001) writes backups; your group can read them for the off-server pull.
sudo install -d -o 10001 -g you -m 750 /srv/compromise-ledger/backups
cp deploy/compose/.env.example deploy/compose/.env
```

Edit `deploy/compose/.env`: set `CL_DOMAIN=ledger.example.org` and
`CL_BACKUP_HOST_DIR=/srv/compromise-ledger/backups`, plus any alert settings (see
[DEVELOPMENT.md](DEVELOPMENT.md)). Then:

```sh
make up
make logs
```

On the first start, the job runs the whole pipeline once (about 6 minutes; NVD's first fetch is
slow) and publishes the site. After that it runs daily at 04:30 UTC. Check:

```sh
curl -s https://ledger.example.org/api/health
docker compose -f deploy/compose/compose.yaml ps
```

If you were running the daily job elsewhere (for example on a Mac with `make schedule`), stop it
there (`make unschedule`) so only the server collects data.

### Alerts

Set up two channels, so a broken source or a job that never ran doesn't go unnoticed:

- **ntfy** sends the details when a health check fails: which source, and why. Pick a
  hard-to-guess topic (`echo "cl-$(openssl rand -hex 12)"`), because anyone who knows a topic on
  ntfy.sh can read it. Subscribe to it in the ntfy app.
- **healthchecks.io** is the dead-man's switch: it alerts when the daily job fails or doesn't
  report at all. Create a check with the cron schedule `30 4 * * *`, time zone UTC, and a grace
  time of 2 hours.

Add both to `deploy/compose/.env` (they are secrets), then run `make up` to apply them:

```sh
CL_NTFY_URL=https://ntfy.sh/<topic>
CL_HEALTHCHECKS_URL=https://hc-ping.com/<uuid>
```

To test them, make one step fail on purpose by pointing vendor resolution at seed data that
doesn't exist, then run the checks. The failed step writes nothing, and the published data is
untouched. Then run the step again normally, and the checks recover:

```sh
c="docker compose -f deploy/compose/compose.yaml exec -T job"
$c env CL_SEEDS_DIR=/nonexistent ledger resolve   # fails
$c ledger check --notify                          # ntfy alert; healthchecks.io goes down
$c ledger resolve && $c ledger check --notify     # healthchecks.io back up
```

## 7. Updating

```sh
cd /srv/compromise-ledger/app
git pull
make up        # rebuilds the images and restarts what changed
```

Data lives in Docker volumes (`lake`, `site`, and Caddy's certificates), so it survives rebuilds.

## 8. Backups

After every daily run, `ledger maintain` expires table history older than 7 days
([ADR 0006](adr/0006-snapshot-retention.md)), then `ledger backup` writes `ledger-<time>.tar.gz`
to the backups directory and keeps the newest seven. It holds the SQLite catalog (copied with SQLite's online backup), the
Iceberg warehouse, and the raw downloads, and takes the same lock as the pipeline, so it never
captures a half-finished write. Exports and the site aren't included; they are rebuilt from the
data.

**Copy them off the server.** A provider's own snapshots are a second layer, not a substitute:
they share the provider's fate and can catch the catalog mid-write. Pull from another machine,
so the server holds no credentials for anything else. Run the pull on a schedule from a machine
you control, at least 15 minutes after the daily run (04:30 UTC).

Give the pull its own SSH key without a passphrase, and restrict that key on the server, since
your admin user can usually run Docker and so is effectively root. Each archive is a full
snapshot, so fetching only the newest one is enough. In `~/.ssh/authorized_keys` on the server:

```
command="cat $(ls -1t /srv/compromise-ledger/backups/ledger-*.tar.gz | head -1)",restrict ssh-ed25519 AAAA... backup pull
```

The key can then fetch the newest backup and nothing else: no shell, no forwarding, no writes.

On Windows, the built-in `ssh` and `tar` are enough. Save this as a `.ps1` file, set the
destination, and schedule it with Task Scheduler (`schtasks /Create /SC DAILY ...`; also tick
"Run task as soon as possible after a scheduled start is missed"):

```powershell
$dest = 'C:\Backups\compromise-ledger'
$key = "$env:USERPROFILE\.ssh\cl_backup"
$tmp = "$dest\incoming.tmp"
New-Item -ItemType Directory -Force $dest | Out-Null
# Through cmd, because Windows PowerShell can corrupt binary output redirected with >.
cmd /c "ssh -T -i `"$key`" -o BatchMode=yes -o StrictHostKeyChecking=accept-new you@SERVER > `"$tmp`""
if ($LASTEXITCODE -ne 0) { exit 1 }
tar -tzf $tmp | Out-Null   # keep only a complete archive
if ($LASTEXITCODE -ne 0) { exit 1 }
Move-Item -Force $tmp "$dest\ledger-$(Get-Date -Format yyyyMMdd).tar.gz"
Get-ChildItem $dest -Filter 'ledger-*.tar.gz' |
  Where-Object LastWriteTime -lt (Get-Date).AddDays(-30) | Remove-Item
```

On Linux or macOS, the same key works with `ssh -T ... > file` from cron or launchd. Without
the forced command, rsync also works (`rsync -rt you@SERVER:/srv/compromise-ledger/backups/
~/backups/compromise-ledger/`); leave out `--delete`, so an emptied server directory can't wipe
your copy. Nothing alerts on a failed pull, so check the newest file now and then.

**Restore** into the same paths: Iceberg metadata records absolute file locations under `/data`.
The job container has the backups directory mounted at `/backups` and runs as the data's owner.

On the same server, after losing or damaging the data:

```sh
make down
docker compose -f deploy/compose/compose.yaml run --rm --no-deps job sh -c \
  'cd /data && rm -rf catalog.db warehouse raw && tar -xzf /backups/ledger-<time>.tar.gz'
make up
# Optional: catch up on missed days and rebuild the site now instead of at 04:30 UTC.
docker compose -f deploy/compose/compose.yaml run --rm job /app/deploy/scripts/daily.sh
```

Pick the newest archive that predates the problem.

On a new server, follow sections 1–6 up to editing `.env` (it isn't in the backup; keep your own
copy), copy an archive into the backups directory, and run the restore command above **before
the first `make up`**. The job decides it is a first start by the missing site, not the missing
data: started first, it would crawl from scratch into an empty lakehouse. Restored first, its
first-start run builds gold, the exports, and the site from your data and fetches the days since
the backup.

## 9. Day-to-day

| To | Run |
|---|---|
| See what's running | `docker compose -f deploy/compose/compose.yaml ps` |
| Follow the logs | `make logs` |
| Run the daily job now | `docker compose -f deploy/compose/compose.yaml exec job /app/deploy/scripts/daily.sh` |
| Health checks | `docker compose -f deploy/compose/compose.yaml exec job ledger check` |
| Stop everything | `make down` (data is kept) |

Reporting a security problem with the project: see [SECURITY.md](../SECURITY.md).
