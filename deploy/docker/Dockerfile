# Two images from one build: `api` (Python only) and `job` (Python plus Node for rebuilding the
# site, and supercronic). Base images are pinned by digest to releases at least 14 days old;
# Renovate proposes updates under the same rule. Both run as an unprivileged user.

FROM ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 AS uv
FROM node:24.21.0-trixie-slim@sha256:173f125896c3b47ddf056734c7ea789d04595a6a08769a8f78e0df642781fb66 AS node
FROM python:3.13.15-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS python

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
COPY pipelines/sql /app/pipelines/sql
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    CL_DATA_DIR=/data \
    CL_EXPORTS_DIR=/data/exports \
    CL_SEEDS_DIR=/app/data/seeds \
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
