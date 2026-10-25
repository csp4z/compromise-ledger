# Architecture

Each component below is grouped by layer, with what it does, what it can grow into, and how it serves the project's three goals:

- **Insight:** trends and events for users.
- **Openness:** open data, open source, open standards.
- **Engineering quality:** a reference implementation of a modern, open-source data platform.

Not everything here runs from day one. The **Phase** and **Profile** lines say when a component is introduced and where it runs. See [ROADMAP.md](ROADMAP.md) and [DEVELOPMENT.md](DEVELOPMENT.md).

A phase is the *earliest* point a component can arrive. Components in Phases 1–2 are added only when the real need named in [ADR 0002](adr/0002-small-stack-and-component-triggers.md) appears. Components in Phases 3–4 are showcase milestones in their own right. Design decisions are recorded in [docs/adr/](adr/).

## Overview

```
 Sources ──► Crawler plugins ──► Event log ──► Orchestration ──► Enrichment
 (clearnet,   (Python, httpx;     (bronze table  (CLI → Dagster)    (entity resolution,
  Tor later)   Playwright if       → NATS → Kafka)                    LLM extraction,
               needed)                                               
                                                                     reference joins)
                                                                          │
                                                                          ▼
                                       Lakehouse: Apache Iceberg on object storage
                                       bronze (raw) → silver (STIX) → gold (marts)
                                                                          │
                     ┌──────────────────┬──────────────────┬──────────────┴───────┐
                     ▼                  ▼                  ▼                      ▼
                DuckDB / ClickHouse   OpenSearch        Graph (optional)     Export bundles
                (analytics)           (search)          (relationships)      (Parquet/CSV/JSON/STIX)
                     │                  │                  │                      │
                     └──────────────────┴────────┬─────────┴──────────────────────┘
                                                 ▼
                                FastAPI REST · GraphQL · TAXII 2.1
                                                 ▼
                                Web app · visualizations · DuckDB-WASM
```

The lakehouse is the single source of truth. Every store to its right is a **projection** that can be rebuilt from it at any time.

## 1. Ingestion

**Crawler plugins** (Python, `httpx`; Playwright only for plugins that need a browser)

- **Does:** fetches raw documents from sources (advisories, news, SEC filings, leak-site listings) and emits them as standardized `RawDocument` records. Each crawler is its own package, registered through a Python entry point, and declares its schedule, rate limit, network (`clearnet` or `tor`), and upstream license.
- **Can:** add sources without touching anything else; handle JavaScript-heavy sites via Playwright; run on independent schedules and rate limits.
- **Why not Scrapy:** Scrapy wants to own the crawl loop, while the plugin contract is a small `fetch → RawDocument` function. Phase 1 sources are JSON and XML APIs.
- **Crawl and parse are separate.** Parser plugins turn stored raw documents into silver records, so a parser fix is replayed from bronze without re-crawling.
- **Serves:** insight comes from source breadth. A small plugin contract keeps each source independent, testable offline, and easy for contributors to add.
- **Phase:** 1 · **Profile:** all

**Tor sidecar** (isolated container, egress proxy)

- **Does:** routes dark-web crawler traffic through Tor, segmented from the rest of the system.
- **Can:** add network policies, request auditing, and kill switches.
- **Serves:** treats threat-intel collection as a security problem in its own right; a compromise of the crawler cannot reach the rest of the system.
- **Phase:** 3 · **Profile:** standard, full

## 2. Transport

**Event log** (bronze table → NATS JetStream → Apache Kafka)

- **Does:** carries "new document" and "new entity" events between stages, decoupling producers from consumers.
- **Can:** replay history to rebuild downstream stores; let new consumers (alerts, webhooks, a social bot) subscribe without changing producers.
- **Serves:** the backbone of the extensibility requirement. Event-driven design is standard at tech companies.
- **Phase 1 note:** crawls are scheduled batches, so the append-only `bronze.raw_documents` Iceberg table *is* the log. Stages read new rows since their last watermark. A broker is added only when a consumer needs events faster than the schedule delivers them.
- **Phase:** 1 (bronze table), 2+ (NATS, when triggered), 4 (Kafka) · **Profile:** lite = bronze table, standard = NATS, full = Kafka

**Schema registry** (Apicurio)

- **Does:** versions the schemas of events flowing through the log and rejects incompatible changes.
- **Can:** enforce backward compatibility as the data model evolves.
- **Serves:** prevents breakage as the project grows, and signals data-contract maturity.
- **Phase:** 4 · **Profile:** full. Until then, schemas live as versioned files in `/schemas`.

## 3. Orchestration

**Dagster**

- **Does:** schedules and runs pipelines as data assets, tracks dependencies and lineage, retries failures, and shows run history in a UI.
- **Can:** add data-quality checks, partitioned backfills, and sensors that trigger on new data.
- **Serves:** the lineage graph is a ready-made demo visual, and it teaches modern data platform engineering.
- **Phase:** 2 (Phase 1 uses a plain Python CLI, `ledger`, run on a schedule; pipeline steps are plain functions so Dagster can wrap them as assets without rewriting them) · **Profile:** standard, full

## 4. Enrichment (where the value is created)

**Entity resolution**

- **Does:** merges name variants into canonical organizations, vendors, and products.
- **Can:** use fuzzy matching, embeddings, and external IDs such as LEI, ticker, or CPE vendor strings.
- **Serves:** without it, trend counts are wrong. The hardest and most impressive data problem in the project.
- **Phase:** 1 (a curated vendor alias table in `data/seeds/`, changed through reviewed PRs, plus a published list of unresolved names), 2 (fuzzy and embedding-based matching) · **Profile:** all

**LLM/NER extraction** (local open-weight models via Ollama or vLLM)

- **Does:** pulls structured facts (victim, date, actor, attack type, affected product) out of unstructured articles.
- **Can:** classify incidents, summarize events, score confidence, and flag contradictions between sources.
- **Serves:** applied AI on real security data, run fully open source.
- **Guardrails:** models are called through an OpenAI-compatible endpoint, so Ollama (local, CPU or Metal) and vLLM (a rented GPU) can be swapped through configuration. A labeled evaluation set exists before the extractor ships. The model and prompt version are recorded in each fact's provenance.
- **Phase:** 2 · **Profile:** standard, full (small models can be tested locally on Apple Silicon)

**Reference joins** (NVD, CISA KEV, OSV, MITRE ATT&CK)

- **Does:** links vendor products to CVEs, known exploitation, and attacker techniques.
- **Can:** add EPSS scores, vendor patch timelines, and time-to-exploit metrics.
- **Serves:** turns the database from a list into analysis — for example, which vendors' flaws get exploited fastest.
- **Phase:** 1 · **Profile:** all

**Dedup and confidence scoring**

- **Does:** collapses duplicate reports and assigns each fact a confidence based on source quality and corroboration.
- **Can:** promote "claimed" facts to "confirmed" as corroboration arrives.
- **Serves:** credibility. A public dataset that labels uncertainty honestly gets cited.
- **Phase:** 1 (basic), 2 (full) · **Profile:** all

## 5. Storage

**Object storage** (local disk → S3-compatible: SeaweedFS self-hosted, S3 on AWS)

- **Does:** holds raw documents and all table files.
- **Can:** run locally, on a single server, on AWS, or anywhere S3-compatible.
- **Serves:** portability between laptop, server, and cloud.
- **Raw documents** are stored content-addressed (`raw/{source_id}/{sha256[:2]}/{sha256}`), so identical fetches are stored once.
- **Phase:** 1 · **Profile:** lite = local disk (S3 opt-in), standard/full = S3-compatible

**Apache Iceberg + catalog** (PyIceberg SQLite catalog → Lakekeeper; see [ADR 0003](adr/0003-iceberg-with-sql-catalog.md))

- **Does:** organizes Parquet files into versioned tables in bronze (raw), silver (normalized STIX), and gold (analytics-ready) layers.
- **Can:** evolve schemas, time-travel ("what did we know on this date?"), and be read by any engine — DuckDB, ClickHouse, Spark, Trino, or Snowflake.
- **Serves:** the single source of truth that makes every other store rebuildable. Gold tables double as the public download.
- **Data model:** silver tables are columnar but STIX-aligned (IDs, vocabularies, relationship shapes). STIX JSON is generated from them and is never the source of truth. IDs are deterministic UUIDv5s, so pipelines are idempotent. See [ADR 0004](adr/0004-stix-aligned-columnar-model.md).
- **Phase:** 1 · **Profile:** lite = SQLite catalog, standard/full = REST catalog (Lakekeeper)

## 6. Serving projections (all rebuildable from Iceberg)

**DuckDB → ClickHouse**

- **Does:** answers aggregate queries fast: incidents per month, per sector, per actor, per vendor.
- **Can:** power materialized views and real-time dashboards (ClickHouse).
- **Serves:** the engine behind the trend visualizations, which are the core insight product.
- **Phase:** 1 (DuckDB), 2+ (ClickHouse, once DuckDB latency or concurrency becomes a measured problem) · **Profile:** lite = DuckDB, standard/full = ClickHouse

**OpenSearch**

- **Does:** full-text search and faceted filtering across organizations, incidents, and advisories.
- **Can:** add semantic search with vector embeddings.
- **Serves:** usability — finding a specific company or vendor quickly.
- **Phase:** added when DuckDB full-text search proves insufficient · **Profile:** full

**Graph store** (optional, NebulaGraph)

- **Does:** models relationships: actor → incident → victim, vendor → product → CVE → incident.
- **Can:** answer path queries such as "which incidents trace back to this vendor's flaws."
- **Serves:** the most visually striking feature. Add it last.
- **Phase:** 4 · **Profile:** full

**Export bundles**

- **Does:** publishes the dataset as Parquet, CSV, JSON, and STIX bundles with version tags.
- **Can:** offer dataset DOIs (e.g., via Zenodo) so researchers can cite specific releases.
- **Serves:** openness drives adoption, and citations build reputation.
- **Manifest:** every release includes `datasets.json`, listing per file the row count, sha256, schema version, Iceberg snapshot ID, license, and sources. Corrections are applied before export.
- **Phase:** 1 (Parquet, CSV, JSON), 3 (STIX bundles) · **Profile:** all

## 7. Access

**FastAPI REST**

- **Does:** documented endpoints for querying and downloading data, with auto-generated OpenAPI docs.
- **Can:** add API keys, rate limiting, and webhooks.
- **Serves:** lets others build on the data. The auto-generated docs are a polished public face.
- **Phase:** 1 · **Profile:** all

**GraphQL** (Strawberry)

- **Does:** flexible queries across related entities in one request.
- **Serves:** relationship-heavy exploration in the frontend.
- **Phase:** 2+ (once profile and timeline pages need relationship queries that REST handles awkwardly) · **Profile:** all

**TAXII 2.1**

- **Does:** serves STIX data in the protocol threat-intel platforms (OpenCTI, MISP) consume.
- **Can:** let security teams subscribe to the feed directly.
- **Serves:** real-world interoperability with practitioner tooling.
- **Phase:** 3 · **Profile:** standard, full

## 8. Presentation

**Web app** (SvelteKit, prerendered; see [ADR 0005](adr/0005-sveltekit-static-frontend.md))

- **Does:** dashboards, organization and vendor profiles, incident timelines, search, and download pages. Static-first: charts and vendor pages are prerendered from gold files and served by Caddy, and the API handles lookups.
- **Can:** add saved views, embeddable charts, and auto-generated weekly reports.
- **Serves:** the public face of the project, where most users meet the data.
- **Phase:** 1 (minimal) · **Profile:** all

**Visualization** (Apache ECharts, Observable Plot)

- **Does:** trend lines, heatmaps, sector breakdowns, vendor scorecards.
- **Serves:** insight made shareable. A good chart travels further than any README.
- **Phase:** 1 · **Profile:** all

**DuckDB-WASM**

- **Does:** lets visitors run SQL against the published Parquet in their own browser.
- **Serves:** a memorable technical demo that also cuts hosting load.
- **Phase:** 2 · **Profile:** all

## 9. Platform and operations

**Docker Compose**

- **Does:** runs the stack locally or on a single server with one command.
- **Serves:** contributors and reviewers can try it in minutes.
- **Phase:** 1 · **Profile:** lite, standard

**k3s / k3d + Helm + Argo CD**

- **Does:** packages every service for Kubernetes and deploys from Git automatically (GitOps).
- **Serves:** portable, reproducible deployment: the same charts run on a laptop cluster, a single server, or the cloud.
- **Phase:** 4 · **Profile:** standard (optional), full

**OpenTofu (AWS modules)**

- **Does:** provisions cloud infrastructure as code for the ephemeral full environment.
- **Serves:** proves cloud deployment capability; spin up for demos, tear down to save money.
- **Phase:** 4 · **Profile:** full

**Crawler health checks** (`ledger check`)

- **Does:** after every run, records the run in `ops.crawl_runs` and fails it if a source returned nothing, parser yield dropped by more than 50% from the previous run, data is past its freshness window, or records fail schema validation. A failure sends a push notification (ntfy) and opens a GitHub issue labeled `crawler-broken`. A healthchecks.io ping acts as a dead-man's switch for the scheduler itself.
- **Serves:** a solo-maintained dataset stays fresh only if breakage is detected automatically. Recorded fixtures turn most repairs into routine work: refresh the fixture, fix the parser, open a PR.
- **Phase:** 1 · **Profile:** all

**Observability** (OpenTelemetry, Prometheus, Grafana, Loki)

- **Does:** traces requests, measures pipeline latency, centralizes logs.
- **Can:** power a public status page showing crawler freshness.
- **Serves:** operational maturity and transparency about data freshness.
- **Phase:** 3 · **Profile:** standard, full

**Secrets** (SOPS + age → OpenBao)

- **Does:** keeps API keys and credentials out of plaintext. Until OpenBao arrives, secrets are SOPS-encrypted files (age keys) decrypted at deploy time. Plaintext `.env` files are local-only and excluded from Git.
- **Serves:** basic security hygiene, without running a secrets server on a single host.
- **Phase:** 1 (SOPS + age), 3 (OpenBao) · **Profile:** OpenBao in standard, full

## 10. Supply-chain security

**GitHub Actions CI, gitleaks, Syft, Trivy, cosign, SLSA provenance, OpenSSF Scorecard, Renovate**

- **Does:** builds, tests, scans for vulnerabilities and leaked secrets, generates SBOMs, signs multi-architecture (amd64 + arm64) images, attests to provenance, and keeps dependencies current.
- **Serves:** the project practices what it catalogs. A database of vendor security failures built with exemplary supply-chain security makes the point on its own.
- **Phase:** 1 (CI, actions pinned by commit SHA, least-privilege tokens, gitleaks, Trivy, Renovate with a 14-day minimum release age, OpenSSF Scorecard), 3 (SBOMs, signing, SLSA) · **Profile:** CI

## How it fits together

- **Insight** is produced by enrichment and delivered by the analytics engine, the web app, and the exports.
- **Openness** is carried by the export bundles, the open APIs, TAXII interoperability, and an all-open-source stack.
- **Engineering quality** is carried by the lakehouse design, swappable backends, portable deployment, and the supply-chain pipeline.

The lakehouse sits at the center: everything upstream feeds it, and everything downstream is a projection that can be rebuilt, swapped, or added. That keeps the project open-ended without becoming fragile.
