# Three images from one build: `api` (Python only), `job` (Python plus Node for rebuilding the
# site, and supercronic), and `caddy` (the official image, made to run unprivileged). Base images are pinned by digest to releases at least 14 days old;
# Renovate proposes updates under the same rule. Both run as an unprivileged user.

FROM ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 AS uv
FROM node:24.21.0-trixie-slim@sha256:173f125896c3b47ddf056734c7ea789d04595a6a08769a8f78e0df642781fb66 AS node
FROM python:3.13.15-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS python
FROM caddy:2.11.6-alpine@sha256:d44355d3c2149dc580ce2cac735955d1c08d3d00882c30489c241aa51a5c10d9 AS caddy-upstream

# The official binary carries a file capability (bind ports below 1024). With all capabilities
# dropped and no-new-privileges, the kernel refuses to exec it. Caddy listens on 8080/8443 here,
# so the capability isn't needed: a plain copy of the binary leaves the attribute behind.
FROM caddy-upstream AS caddy
RUN cp /usr/bin/caddy /usr/bin/caddy.plain && mv /usr/bin/caddy.plain /usr/bin/caddy

# Build the uv workspace into a virtualenv; packages are installed, not linked to the sources.
FROM python AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY schemas schemas
COPY crawlers crawlers
COPY pipelines pipelines
COPY api api
RUN uv sync --frozen --all-packages --no-dev --no-editable

FROM python AS runtime
RUN groupadd --gid 10001 ledger \
    && useradd --uid 10001 --gid ledger --create-home --home-dir /home/ledger ledger \
    && mkdir -p /data /srv/site \
    && chown ledger:ledger /data /srv/site
COPY --from=build /app/.venv /app/.venv
COPY data/seeds /app/data/seeds
COPY data/corrections /app/data/corrections
COPY pipelines/sql /app/pipelines/sql
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    CL_DATA_DIR=/data \
    CL_EXPORTS_DIR=/data/exports \
    CL_SEEDS_DIR=/app/data/seeds \
    CL_CORRECTIONS_FILE=/app/data/corrections/corrections.csv \
    CL_GOLD_SQL_DIR=/app/pipelines/sql/gold
WORKDIR /app

FROM runtime AS api
ENV CL_API_HOST=0.0.0.0 CL_API_PORT=8000
USER 10001:10001
EXPOSE 8000
CMD ["ledger-api"]

FROM runtime AS job
ARG TARGETARCH
COPY deploy/docker/install-supercronic.py /tmp/
RUN python /tmp/install-supercronic.py "${TARGETARCH}" && rm /tmp/install-supercronic.py
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/corepack /usr/local/lib/node_modules/corepack
ENV COREPACK_HOME=/opt/corepack COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN ln -s ../lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
    && corepack enable pnpm \
    && install -d -o ledger -g ledger /opt/corepack
COPY --chown=ledger:ledger web /app/web
COPY deploy/scripts /app/deploy/scripts
COPY deploy/compose/crontab /app/deploy/crontab
USER 10001:10001
# pnpm and the site's dependencies are fetched at build time; the job needs no npm access later.
RUN cd /app/web && corepack install && pnpm install --frozen-lockfile
CMD ["/app/deploy/scripts/job-entrypoint.sh"]
