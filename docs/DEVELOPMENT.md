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
/web           frontend
/data/seeds    curated reference data (security-vendor list, vendor aliases), changed through PRs
/deploy        compose files, Helm charts, OpenTofu modules
/docs          project documentation and ADRs (/docs/adr)
```

## Getting started

Prerequisites:

- [uv](https://docs.astral.sh/uv/). It also installs the right Python (3.13 for development, per `.python-version`; 3.12 is the minimum), so a system Python isn't needed.
- [pnpm](https://pnpm.io/), for the web frontend (once `/web` exists).
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
```

Each run is recorded in `ops.crawl_runs`, and the command exits non-zero if it failed. Data goes
under `.lake/` by default (git-ignored): `raw/` for blobs, `warehouse/` for Iceberg files, and
`catalog.db` for the SQLite catalog. Delete the directory to start over; everything is rebuilt
from the sources.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CL_PROFILE` | `lite` | Backend defaults (see the table above) |
| `CL_DATA_DIR` | `.lake` | Local data directory |
| `CL_STORAGE` | per profile | `local` or `s3` (S3 is not implemented yet) |
| `CL_CATALOG_URI` | `sqlite:///<data dir>/catalog.db` | Iceberg SQL catalog |
| `CL_WAREHOUSE` | `file://<data dir>/warehouse` | Iceberg warehouse location |
| `CL_CRAWLER_CONTACT` | the repo's issues URL | Contact in the crawler User-Agent |
| `CL_SEEDS_DIR` | `data/seeds` | Curated seed data (run from the repo root) |

Most `lite` work runs natively through `uv run`. Containers are needed only to try the production-like stack.

## Testing

Tests never touch the network. Each parser is tested against recorded responses stored in its plugin's `fixtures/` directory. When an upstream format changes, refresh the fixture, fix the parser, and add a regression test.

## Security

Deployment and operations security guidance for self-hosters will live in `docs/SELF_HOSTING.md`. Report vulnerabilities as described in `SECURITY.md`.
