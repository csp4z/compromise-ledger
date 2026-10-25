# ADR 0003: Apache Iceberg with a SQL catalog

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

The lakehouse is the source of truth, and every serving layer must be rebuildable from it. The
options considered for Phase 1 were:

- **Plain Parquet files.** The simplest option, but it has no snapshots, no safe schema
  evolution, no row-level upserts, and no transactional commits. Moving to a table format later
  would mean rewriting the storage layer and every writer.
- **Apache Iceberg.** Snapshots support time travel, which matters here for provenance ("what did
  we know, when") and for auditable corrections. It also provides schema evolution, upserts, and
  broad engine support (DuckDB, ClickHouse, Trino, Spark).

Iceberg needs a catalog. The REST catalogs (Apache Polaris, Lakekeeper) are separate services,
and Polaris runs on the JVM. Phase 1 has a single writer, the `ledger` CLI.

## Decision

- All bronze, silver, gold, and ops tables are Iceberg tables, written with **PyIceberg**.
- The catalog is PyIceberg's **`SqlCatalog` backed by SQLite**, configured from the environment.
  No catalog service runs.
- The warehouse location is configurable: `file://` for local development, `s3://` (SeaweedFS)
  in Compose and on the public server.
- DuckDB reads tables through scans that PyIceberg resolves (Arrow), or through `iceberg_scan` on
  the current metadata location.
- When ADR 0002's Lakekeeper trigger fires, the catalog moves to **Lakekeeper** (Rust,
  Apache-2.0, a smaller footprint than Polaris). That is a configuration change for writers, not
  a code change.

## Consequences

- No extra service or memory cost in Phase 1.
- Only one writer at a time is safe on SQLite. The CLI schedule runs steps sequentially, so this
  is acceptable until Phase 2.
- DuckDB can't attach a SQL catalog directly, so readers go through a small helper that resolves
  table locations. This friction is expected and is one of the Lakekeeper triggers.
- Snapshot expiry is part of the corrections process. Removing a record also expires the
  snapshots that contain it (see `CORRECTIONS.md`).
- The SQLite catalog file is backed up together with the warehouse. Losing it orphans the tables'
  metadata pointers.
