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
sudo apt install -y unattended-upgrades git make
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
sudo install -d -o 10001 -g 10001 /srv/compromise-ledger/backups
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

## 7. Updating

```sh
cd /srv/compromise-ledger/app
git pull
make up        # rebuilds the images and restarts what changed
```

Data lives in Docker volumes (`lake`, `site`, and Caddy's certificates), so it survives rebuilds.

## 8. Backups

After every daily run, `ledger backup` writes `ledger-<time>.tar.gz` to the backups directory and
keeps the newest seven. It holds the SQLite catalog (copied with SQLite's online backup), the
Iceberg warehouse, and the raw downloads, and takes the same lock as the pipeline, so it never
captures a half-finished write. Exports and the site aren't included; they are rebuilt from the
data.

**Copy them off the server.** A provider's own snapshots are a second layer, not a substitute:
they share the provider's fate and can catch the catalog mid-write. Pull from another machine,
so the server holds no credentials for anything else:

```sh
rsync -a --delete you@SERVER:/srv/compromise-ledger/backups/ ~/backups/compromise-ledger/
```

Run that on a schedule from a machine you control (a cron job, or launchd on a Mac).

**Restore** into the same paths: Iceberg metadata records absolute file locations under `/data`.

```sh
make down
docker compose -f deploy/compose/compose.yaml run --rm --no-deps job sh -c \
  'cd /data && rm -rf catalog.db warehouse raw && tar -xzf /backups/ledger-<time>.tar.gz'
make up
```

The job container has the backups directory mounted at `/backups` and runs as the data's owner.

## 9. Day-to-day

| To | Run |
|---|---|
| See what's running | `docker compose -f deploy/compose/compose.yaml ps` |
| Follow the logs | `make logs` |
| Run the daily job now | `docker compose -f deploy/compose/compose.yaml exec job /app/deploy/scripts/daily.sh` |
| Health checks | `docker compose -f deploy/compose/compose.yaml exec job ledger check` |
| Stop everything | `make down` (data is kept) |

Reporting a security problem with the project: see [SECURITY.md](../SECURITY.md).
