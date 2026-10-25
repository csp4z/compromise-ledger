# Project Brief

## Purpose

Compromise Ledger is an open reference dataset and analytics site for security incidents and security-vendor product flaws. It has three goals:

1. **Insight** — give people a clear, sourced view of security incidents and vendor product flaws, and the trends across them.
2. **Openness** — open data, open source, and open standards (STIX 2.1, TAXII 2.1), so the dataset can be inspected, reused, and integrated into other tools.
3. **Engineering quality** — serve as a reference implementation of a modern, open-source data platform: lakehouse storage, event-driven pipelines, portable deployment, and strong supply-chain security.

## Scope

**In scope**

- Organizations that have suffered cyber attacks: incidents, dates, claimed or attributed threat actors, sources.
- Security vendors whose own products had security issues: advisories, CVEs, known exploitation.
- Trend analysis and visualization.
- Downloadable data and source references via the site and API.

**Out of scope**

- Leaked data, dumps, or stolen files of any kind.
- Personal information about individuals affected by breaches.
- Attribution claims beyond what sources state.

## Data sources

- **Clearnet:** CISA KEV, NVD, OSV, MITRE ATT&CK, vendor security advisories, SEC 8-K Item 1.05 filings, state breach notifications, security news.
- **Tor (later phase):** ransomware leak-site listings — metadata only. See [DATA_POLICY.md](DATA_POLICY.md).

## Constraints

- **Open source only (OSI-approved).** Avoid source-available/BSL tools:
  - OpenTofu, not Terraform
  - OpenBao, not Vault
  - Apache Kafka or NATS, not Redpanda
  - Valkey over Redis
  - SeaweedFS or Garage over MinIO
- **Lakehouse-centric.** Apache Iceberg is the source of truth; no traditional relational database as the core store.
- **Extensible.** New crawlers, enrichment steps, stores, and views plug in without modifying existing components.
- **Backend-swappable.** Storage, transport, and search sit behind interfaces selected by a runtime profile (see [DEVELOPMENT.md](DEVELOPMENT.md)).
- **Portable.** The same code and deployment definitions run on a laptop, a single server, or Kubernetes in the cloud.
- **Lean first.** A component is added only when a real need requires it, not because it appears on the architecture diagram. See [ADR 0002](adr/0002-small-stack-and-component-triggers.md).
- **Ethical by design.** Metadata only, provenance on every fact, claims labeled as claims, and a published corrections process. See [DATA_POLICY.md](DATA_POLICY.md).

## Success criteria

- A public site with useful, sourced trend data, updated automatically.
- A dataset others can download, cite, and integrate.
- A codebase that is well documented, tested, and easy to run from a fresh clone.

## A note on scale

The data is small: NVD holds roughly 300,000 CVEs and KEV about 1,500 entries, and even leak-site listings run to tens of thousands a year. All of it fits in DuckDB on a laptop. The lakehouse and the other platform components are here for what they provide (versioned history, schema evolution, rebuildable projections, portability) and as a reference implementation. Data volume doesn't require them. Each one's reason is recorded in [docs/adr/](adr/).
