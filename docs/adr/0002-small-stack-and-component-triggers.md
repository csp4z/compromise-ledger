# ADR 0002: Small stack and component triggers

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

The target architecture includes Kafka, a schema registry, Dagster, ClickHouse, OpenSearch, a
graph database, a REST catalog service, OpenBao, Kubernetes, and Argo CD. Each one is a
stateful service that needs upgrades, backups, and monitoring, and one person maintains all of
them.

The data is also small. NVD holds roughly 300k CVEs, CISA KEV about 1.5k entries, SEC 8-K Item
1.05 filings number in the hundreds per year, and ransomware leak-site posts in the tens of
thousands per year. All of it fits comfortably in DuckDB on a laptop.

Development happens on an 8 GB laptop until a single server is set up for public hosting.

## Decision

Phase 1 runs on this stack only:

- Python crawlers using `httpx` (no Scrapy; Playwright only for plugins that need a browser)
- Apache Iceberg via PyIceberg with a SQL catalog (ADR 0003)
- Local filesystem storage in development; SeaweedFS (S3-compatible, Apache-2.0) on the public
  server. Garage was considered, but it is AGPL and has more gaps in S3 API coverage.
- SOPS + age for secrets
- DuckDB for transformations and analytics
- A `ledger` CLI run on a schedule (supercronic in Compose)
- FastAPI (read-only) and a static-first web frontend behind Caddy
- Docker Compose for deployment

Every further component has an earliest phase (from [ROADMAP.md](../ROADMAP.md)) and a trigger.

- **Phases 1–2:** a component is added only once its phase has been reached **and** its trigger
  occurs. Reaching the phase alone is not enough.
- **Phases 3–4:** the component is that phase's showcase milestone. Reaching the phase is the trigger.

Each addition is recorded in a new ADR that cites its trigger.

| Component | Earliest phase | Trigger |
|---|---|---|
| Dagster | 2 | More than 5 sources, or cross-source dependencies or backfills become painful through the CLI |
| Lakekeeper (REST catalog) | 2 | DuckDB, ClickHouse, or Trino needs REST catalog access, or there is more than one writer |
| ClickHouse | 2 | API p95 latency above 500 ms on DuckDB, or concurrent dashboard load |
| NATS JetStream | 2 | A consumer needs events sooner than the batch schedule delivers them |
| GraphQL | 2 | Profile and timeline pages need relationship queries that REST handles awkwardly |
| Local LLM extraction (Ollama) | 2 | Free text needs fields that rules or CSAF can't provide, **and** a labeled evaluation set exists |
| OpenSearch | 2 | Full-text search across advisories and filings that DuckDB FTS can't serve well |
| Tor runner | 3 | The corrections process has handled at least one real request |
| TAXII 2.1, OpenBao, observability stack, signing/SBOM/SLSA | 3 | Phase 3 milestones |
| Kubernetes, Helm, Argo CD, OpenTofu on AWS, Kafka, Apicurio | 4 | Phase 4 milestones; the AWS stack runs as a temporary apply/destroy demo |
| Graph database | 4 (optional) | DuckDB recursive CTEs plus precomputed edge lists can no longer drive the relationship explorer |

## Consequences

- Phase 1 runs in roughly 1.5 GB of RAM and can be shipped publicly within about a month.
- Pipeline steps are written as plain functions callable from the CLI, so Dagster can wrap them as
  assets later without rewriting them.
- Backends sit behind the runtime-profile interfaces described in
  [DEVELOPMENT.md](../DEVELOPMENT.md), so adding a component is a new adapter plus configuration,
  not a change to existing code.
- The showcase components still arrive, each as its own milestone with a documented reason. That
  is a stronger story than shipping them all at once.
- Risk: a trigger can fire later than ideal. That is acceptable. Adding a component when it is
  needed costs less than running one before it is.
