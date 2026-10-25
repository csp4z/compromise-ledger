# Development

## Runtime profiles

The application code is the same everywhere. A **profile** setting selects which backends it uses, so heavier components can be swapped in without code changes.

| Concern | `lite` | `standard` | `full` |
| --- | --- | --- | --- |
| Intended for | Laptop development | Single server | Kubernetes in the cloud |
| Iceberg catalog | PyIceberg SQLite catalog | Lakekeeper | Lakekeeper |
| Object storage | Local disk | SeaweedFS | S3 |
| Analytics | DuckDB | ClickHouse | ClickHouse |
| Search | DuckDB full-text search | DuckDB full-text search | OpenSearch |
| Events | Bronze Iceberg table | NATS JetStream | Kafka (Strimzi) |
| Orchestration | Python CLI | Dagster | Dagster |
| Secrets | SOPS + age | OpenBao | OpenBao |
| Runtime | Docker Compose | Docker Compose or k3s | Kubernetes via Helm |

**Design rule:** storage, transport, and search sit behind small interfaces. Selecting a backend is configuration (e.g., `CL_PROFILE=lite`), never a code change.

A profile sets defaults, and each concern can be overridden on its own. For example, the Phase 1 public server runs `lite` with `CL_STORAGE=s3` against SeaweedFS. Components in the `standard` and `full` columns are added as the [roadmap](ROADMAP.md) reaches them, so early on a profile may not have every backend yet.

## Requirements

| Profile | Approximate memory | Notes |
| --- | --- | --- |
| `lite` | 8GB machine (about 4GB for containers) | Runs on a typical laptop |
| `standard` | 16GB | Adds ClickHouse, NATS, Dagster |
| `full` | 32GB, or a Kubernetes cluster | Adds Kafka and OpenSearch |

Any OCI-compatible container runtime works: Docker, Colima, or Podman.

## The `full` environment

`full` is designed to be **ephemeral**: provisioned on demand, used, and torn down.

- Infrastructure is defined with OpenTofu; services are deployed with the same Helm charts used everywhere else.
- On startup it hydrates from the lakehouse: Kafka replays from bronze tables, OpenSearch indexes from gold tables. Nothing is lost on teardown.
- Deployments carry an expiry tag, and a scheduled workflow removes expired environments.

## Multi-architecture builds

All images are built for both `linux/amd64` and `linux/arm64`, so the stack runs on Apple Silicon, ARM cloud instances, and x86 servers alike.

## Repository layout

```
/crawlers      crawler SDK (/crawlers/sdk) and plugins (one package per source)
/pipelines     parsing, enrichment, and transformation jobs; gold views as SQL files
/schemas       STIX-aligned data contracts (versioned)
/api           FastAPI service (REST; later GraphQL, TAXII)
/web           SvelteKit site, prerendered from the gold exports (ADR 0005)
/data/seeds    curated reference data (security-vendor list, vendor aliases), changed through PRs
/deploy        compose files, Helm charts, OpenTofu modules
/docs          project documentation and ADRs (/docs/adr)
```

## Getting started

Prerequisites:

- [uv](https://docs.astral.sh/uv/). It also installs the right Python (3.13 for development, per `.python-version`; 3.12 is the minimum), so a system Python isn't needed.
- Node 24 and [pnpm](https://pnpm.io/) for the web frontend (`corepack enable` installs the pinned pnpm).
- Later, an OCI-compatible container runtime. On macOS, [Colima](https://github.com/abiosoft/colima) is a fully open-source option; give its VM 3–4 GB of memory for `lite`.

```sh
git clone https://github.com/csp4z/compromise-ledger.git
cd compromise-ledger
make dev     # installs the Python workspace and the git hooks (pre-commit comes with the dev dependencies)
make check   # lint, type check, and tests: the same checks CI runs
```

Run `make` with no target to list everything available.

The Python code is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): `ledger-schemas`, `ledger-crawl`, `ledger-pipelines`, and `ledger-api` are separate packages sharing one lockfile. Dependency resolution ignores anything uploaded in the last 14 days (`exclude-newer`), which limits exposure to compromised fresh releases.

_Target for the end of Phase 1a: the same `make dev` reaches a running `lite` stack in under 10 minutes._

### Running a source

```sh
uv run ledger sources            # registered crawlers, schedules, licenses
uv run ledger crawl cisa-kev     # fetch into raw blobs + bronze.raw_documents
uv run ledger parse cisa-kev     # latest raw document -> silver tables
uv run ledger resolve            # vendor names -> data/seeds/ vendors; rebuild products
uv run ledger build gold         # corrections applied, then pipelines/sql/gold/ -> gold.*
uv run ledger export             # rebuild gold, write files + datasets.json to .lake/exports/
uv run ledger check              # health checks; --notify also sends alerts
uv run ledger run daily          # all of the above for every source, then check and alert
```

Each run is recorded in `ops.crawl_runs`, and the command exits non-zero if it failed. Each step
is logged as it starts and finishes. Commands that write take a lock on `<data dir>/ledger.lock`,
because the SQLite catalog allows one writer; a second one exits with code 75 and changes nothing. Data goes
under `.lake/` by default (git-ignored): `raw/` for blobs, `warehouse/` for Iceberg files,
`catalog.db` for the SQLite catalog, and `exports/` for the published files. Delete the directory to start over; everything is rebuilt
from the sources.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CL_PROFILE` | `lite` | Backend defaults (see the table above) |
| `CL_DATA_DIR` | `.lake` | Local data directory |
| `CL_STORAGE` | per profile | `local` or `s3` (S3 is not implemented yet) |
| `CL_CATALOG_URI` | `sqlite:///<data dir>/catalog.db` | Iceberg SQL catalog |
| `CL_WAREHOUSE` | `file://<data dir>/warehouse` | Iceberg warehouse location |
| `CL_CRAWLER_CONTACT` | `contact5@kuricove.com` | Contact in the crawler User-Agent |
| `CL_SEEDS_DIR` | `data/seeds` | Curated seed data (run from the repo root) |
| `CL_EXPORTS_DIR` | `<data dir>/exports` | Export files and `datasets.json` |
| `CL_NTFY_URL` | unset | ntfy topic URL for failure alerts (secret) |
| `CL_GITHUB_TOKEN` | unset | Token that opens or comments on a `crawler-broken` issue (secret; needs Issues write) |
| `CL_GITHUB_REPO` | `csp4z/compromise-ledger` | Repository for those issues |
| `CL_HEALTHCHECKS_URL` | unset | healthchecks.io ping URL: the scheduler's dead-man's switch (secret) |

`ledger check` fails a source when its latest crawl or parse failed, it returned nothing, its
parse yield fell below half the previous good parse, or its last good crawl is older than
`CrawlerMeta.max_age_hours` (default 36). Alert settings are secrets: keep them in a local
`.env` or the SOPS-encrypted deploy config, never in Git.

### The API and the site

Both read the gold export (`.lake/exports/` by default, or `CL_EXPORTS_DIR`), never the lakehouse.

```sh
make api                                        # http://127.0.0.1:8000, OpenAPI docs at /docs
make web                                        # static site in web/build/
cd web && pnpm dev                              # live-reloading site on http://localhost:5173
cd web && CL_EXPORTS_DIR=../tests/sample-exports pnpm build   # without local data
```

`pnpm build` copies the export into the site under `/files/`, refusing any file whose checksum
doesn't match `datasets.json`, so the downloads always match the manifest. npm packages follow
the same 14-day minimum release age as Python (`minimumReleaseAge` in `web/pnpm-workspace.yaml`).

### Scheduling the daily run on macOS

Until the public server exists, the daily job can run on a Mac with launchd:

```sh
make schedule                      # daily at 21:30 local; CL_DAILY_HOUR=6 make schedule to change
deploy/launchd/install.sh run      # run now
deploy/launchd/install.sh status   # loaded? last exit code?
make unschedule                    # remove it
```

The installer writes a per-user LaunchAgent from `deploy/launchd/daily.plist.in`. The generated
plist holds local paths, so it is never committed. The job runs `.venv/bin/ledger run daily`
against `.lake/`, logs to `.lake/logs/daily.log`, and starts on wake if the Mac was asleep at the
scheduled time. Crawlers' own `schedule` fields aren't used yet: every source runs once per daily
job. On the server, the same command runs under supercronic in Compose (ADR 0002).

Most `lite` work runs natively through `uv run`. Containers are needed only to try the production-like stack.

## Testing

Tests never touch the network. Each parser is tested against recorded responses stored in its plugin's `fixtures/` directory. When an upstream format changes, refresh the fixture, fix the parser, and add a regression test.

## Security

Deployment and operations security guidance for self-hosters will live in `docs/SELF_HOSTING.md`. Report vulnerabilities as described in `SECURITY.md`.
