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

_To be written once the Phase 1 scaffold exists. Target: one command (`make dev`) from clone to a running `lite` stack in under 10 minutes._

Planned prerequisites:

- [uv](https://docs.astral.sh/uv/) (Python 3.12+ and dependencies)
- [pnpm](https://pnpm.io/) (web frontend)
- [pre-commit](https://pre-commit.com/) (lint, format, and secret-scanning hooks)
- An OCI-compatible container runtime. On macOS, [Colima](https://github.com/abiosoft/colima) is a fully open-source option; give its VM 3–4 GB of memory for `lite`.

Most `lite` work runs natively through `uv run`. Containers are needed only to try the production-like stack.

## Testing

Tests never touch the network. Each parser is tested against recorded responses stored in its plugin's `fixtures/` directory. When an upstream format changes, refresh the fixture, fix the parser, and add a regression test.

## Security

Deployment and operations security guidance for self-hosters will live in `docs/SELF_HOSTING.md`. Report vulnerabilities as described in `SECURITY.md`.
