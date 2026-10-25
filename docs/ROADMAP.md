# Roadmap

The project is built in phases. Each phase ends with something public and a **phase gate**: explicit criteria that must be met before starting the next phase. If a phase runs long, cut scope rather than start the next one early.

**Rule:** a component is added only when a real need requires it, not because it appears in [ARCHITECTURE.md](ARCHITECTURE.md). The needs that justify each component are listed in [ADR 0002](adr/0002-small-stack-and-component-triggers.md).

## Phase 1 — Lean MVP (target: ~4 weeks for 1a, ~7 weeks for 1b)

**Goal:** real data, a public dashboard, and downloadable files.

Phase 1 ships publicly twice, so the first release isn't held back by the slowest source.

### 1a — Security vendors' own products in KEV

The launch angle: CISA KEV and NVD are widely visualized, but rarely through the lens of *security vendors' own products* being exploited. That angle is this project's second goal.

**Deliverables**

- Monorepo scaffold: `/crawlers`, `/pipelines`, `/schemas`, `/api`, `/web`, `/deploy`, `/docs`.
- Crawler plugin interface (crawl and parse as separate plugins) with offline, fixture-based tests.
- Crawlers: CISA KEV and NVD (API 2.0, incremental).
- Initial STIX-aligned schema: Vendor, Product, Vulnerability, Relationship, Provenance, Correction.
- Curated security-vendor list and vendor alias table (`data/seeds/`), plus a published list of unresolved vendor names.
- Iceberg tables (bronze/silver/gold) with a local SQLite catalog; DuckDB for queries.
- Basic dedup and provenance on every record.
- Crawler health checks with alerts when a source returns nothing or yield drops sharply.
- Exports: Parquet, CSV, and JSON with a checksummed `datasets.json` manifest.
- FastAPI (read-only) with OpenAPI docs.
- Minimal web app: security-vendor KEV leaderboard and timeline, ransomware-use share, time from CVE publication to KEV addition, and download links.
- Data policy and corrections process published (see [DATA_POLICY.md](DATA_POLICY.md) and [CORRECTIONS.md](../CORRECTIONS.md)).
- Docker Compose for local and single-server runs (`lite` profile, with S3-compatible storage on the server).
- CI: lint, type checks, tests, gitleaks, Trivy scan, OpenSSF Scorecard, Renovate. Actions pinned by commit SHA.

**Progress (as of 2026-10-25)**

Built:

- Crawler SDK (plugin contract, etiquette and data-policy enforcement, opt-in retries, snapshot and
  incremental parsers) with offline fixture tests.
- Crawlers: CISA KEV, and NVD limited to CVEs in KEV (`hasKev`). The full NVD set comes later.
- Schemas, deterministic IDs, and JSON Schema; the curated vendor list and aliases (283 vendors,
  20 security vendors by the primary-business rule); vendor resolution with the unresolved list.
- Lakehouse: Iceberg bronze/silver/gold on the SQLite catalog; DuckDB gold SQL; corrections applied
  before every gold build; Parquet/CSV/JSON exports with a checksummed `datasets.json`.
- `ledger run daily` and `ledger check` (health checks, with ntfy, GitHub-issue, and
  healthchecks.io alerts available but not yet switched on), scheduled daily on a Mac with
  launchd.
- Read-only FastAPI and the prerendered SvelteKit site (dashboard, data, method), both reading
  the gold exports only.

Still to do for 1a, in rough order:

1. **Hosting:** a server with Docker Compose (Caddy for the site and API, supercronic for the
   daily job), the site rebuilt after each export, and the domain decision.
2. **Corrections:** a way to record corrections (today `silver.corrections` is applied but has no
   entry path), and expiring the Iceberg snapshots that contain a removed record.
3. **Alerts:** switch them on, and verify them by breaking a fixture on purpose (gate item).
4. **Contact addresses:** a project email for the private corrections contact and the crawler
   User-Agent (currently the repo's issues URL).
5. **Fresh-clone test:** time `git clone` to a running `lite` stack (gate: under 10 minutes).

The 7-day KEV and NVD refresh count starts with the first scheduled run that includes NVD
(2026-10-25, 21:30 local).

**Cut list if behind, in this order:** S3 storage on the server (stay on local disk) → FastAPI (ship static files and downloads only) → NVD (launch KEV-only).

**Gate 1a**

- [ ] Public site live with at least one trend chart worth sharing.
- [ ] Daily KEV and NVD refreshes ran for 7 consecutive days without manual intervention; alerting verified by breaking a fixture on purpose.
- [ ] Data downloadable as Parquet and CSV; manifest checksums match the files.
- [ ] A fresh clone reaches a running `lite` stack in under 10 minutes.
- [ ] Private corrections contact address published in [CORRECTIONS.md](../CORRECTIONS.md).

### 1b — Organizations attacked

**Deliverables**

- SEC 8-K Item 1.05 crawler (material cybersecurity incidents).
- A generic CSAF 2.0 advisory crawler, covering many vendors through their `provider-metadata.json`.
- Organization and Incident schemas, with incident status (claimed, reported, confirmed) and a STIX extension definition for incidents.
- Incident timeline page.

**Phase gate**

- [ ] Crawlers run on a schedule without manual intervention for 2 weeks.
- [ ] README and docs accurate for a new reader.

## Phase 2 — Depth

**Goal:** data quality and richer exploration.

**Deliverables**

- Entity resolution for organizations, vendors, and products, beyond the curated alias table.
- LLM-assisted extraction from unstructured articles, with a labeled evaluation set built first.
- Full confidence scoring and claimed/reported/confirmed status transitions.
- Dagster orchestration replacing the CLI runner.
- Additional CVE sources: CVE List V5 and CISA Vulnrichment, to fill gaps in NVD enrichment.
- Organization and vendor profile pages.
- DuckDB-WASM in-browser SQL.
- `standard` profile components (ClickHouse, NATS, Lakekeeper) and GraphQL, each added when its ADR 0002 need appears rather than by default.

**Phase gate**

- [ ] Entity resolution measurably reduces duplicates (tracked metric).
- [ ] Every published fact carries source, crawl time, and confidence.
- [ ] Crawler failures are detected automatically within 24 hours.

## Phase 3 — Credibility

**Goal:** threat-intel interoperability and hardened security engineering.

**Deliverables**

- Tor leak-site metadata crawlers in an isolated container (per [DATA_POLICY.md](DATA_POLICY.md)). Starts only after the corrections process has handled at least one real request.
- TAXII 2.1 feed; STIX bundle exports.
- Supply-chain pipeline: SBOMs, cosign-signed multi-arch images, SLSA provenance.
- OpenBao for secrets; observability stack with a public status page.

**Phase gate**

- [ ] TAXII feed consumed successfully by OpenCTI or MISP.
- [ ] Signed images and SBOMs verifiable from the README instructions.
- [ ] Leak-site crawlers verified to fetch listing pages only (tests prove file links are never followed).

## Phase 4 — Scale and portability

**Goal:** portable Kubernetes deployment and advanced exploration.

**Deliverables**

- Helm charts for every service; Argo CD GitOps.
- OpenTofu modules for the ephemeral AWS `full` environment, with auto-teardown and a budget alert.
- Kafka (Strimzi), Apicurio schema registry, and OpenSearch via operators in the `full` profile.
- Optional graph store and relationship explorer.
- Automated weekly trend report.

**Phase gate**

- [ ] `full` environment deploys and tears down from one command or workflow.
- [ ] The same Helm charts run on local k3d, a single server, and AWS.

## Decisions

| Decision | Status | Where recorded |
| --- | --- | --- |
| Table format and catalog | Decided: Apache Iceberg; SQLite catalog in Phase 1, Lakekeeper when needed | [ADR 0003](adr/0003-iceberg-with-sql-catalog.md) |
| Data model and IDs | Decided: STIX-aligned columnar tables, deterministic UUIDv5 IDs | [ADR 0004](adr/0004-stix-aligned-columnar-model.md) |
| Code license | Decided: Apache-2.0 | [LICENSE](../LICENSE) |
| Dataset license | Decided: CC BY 4.0 | [LICENSE-DATA](../LICENSE-DATA) |
| Object storage | Decided: SeaweedFS | [ADR 0002](adr/0002-small-stack-and-component-triggers.md) |
| Frontend framework | Decided: SvelteKit, prerendered from the gold exports | [ADR 0005](adr/0005-sveltekit-static-frontend.md) |
| Domain name | Pending: compromiseledger.\* Needed by Phase 1a. | — |
