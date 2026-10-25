#!/bin/sh
# Build the site from the current export into a new release and switch to it atomically:
# Caddy serves /srv/site/current, a symlink, so visitors never see a half-written site.
set -eu
releases=/srv/site/releases
release="${releases}/$(date -u +%Y%m%dT%H%M%SZ)"
cd /app/web
pnpm build
mkdir -p "${releases}"
cp -R build "${release}"
ln -sfn "${release}" /srv/site/current.next
mv -T /srv/site/current.next /srv/site/current
# Keep the three newest releases.
ls -1d "${releases}"/* | head -n -3 | xargs -r rm -rf
echo "site: published ${release}"
