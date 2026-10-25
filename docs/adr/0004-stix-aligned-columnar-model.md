# ADR 0004: STIX-aligned columnar model with deterministic IDs

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

The dataset should interoperate with threat-intelligence tooling, so the canonical model is
aligned to STIX 2.1. STIX is an *exchange* format, though: objects are nested JSON documents with
embedded lists, linked by relationship objects. Storing STIX JSON directly would make analytics
awkward and schema evolution fragile.

Pipelines are rerun often (re-parsing bronze after a parser fix, backfills), so the same
real-world entity must always get the same ID.

## Decision

1. **Columnar tables, STIX-aligned.** Silver tables are typed, columnar Iceberg tables whose
   names, ID formats, vocabularies, and relationship shapes follow STIX 2.1:

   | Table | STIX type |
   |---|---|
   | `vulnerabilities` | `vulnerability` |
   | `vendors`, `organizations` | `identity` (`identity_class: organization`) |
   | `products` | `software` |
   | `incidents` | `incident` |
   | `threat_actors` | `threat-actor` / `intrusion-set` |
   | `relationships` | `relationship` (with `confidence`, `start_time`, `stop_time`) |

2. **STIX is a projection.** STIX bundles (and later the TAXII 2.1 feed) are generated from the
   tables by an exporter. STIX JSON is never the source of truth.
3. **Extensions for project-specific data.** Properties STIX doesn't define (KEV status, claim
   status, the full provenance struct) go in STIX 2.1 Extension Definitions published with the
   project. The 2.1 `incident` SDO is minimal, so it gets a project extension too.
4. **Deterministic IDs.** Every domain object's ID is `<stix-type>--<uuid5(PROJECT_NAMESPACE, natural_key)>`,
   generated only by `ledger_schemas.make_id()`. Natural keys are documented per type (for
   example the CVE ID for vulnerabilities, the canonical vendor slug for vendors).
5. **Confidence** uses the STIX scale: an integer from 0 to 100.

## Consequences

- Re-parsing and re-running pipelines are idempotent, and upserts by ID are safe.
- **Deviation from the spec:** STIX 2.1 recommends UUIDv4 for SDOs and SROs. This is a SHOULD,
  not a MUST, and UUIDv5 is still a valid RFC 4122 UUID. The project accepts the deviation for
  idempotency and documents it here.
- Natural keys have to be stable. A changed canonical vendor slug would produce a new ID, so
  renames go through the alias table instead of changing the slug.
- Analytics stay plain SQL over flat tables, and STIX consumers still receive valid bundles.
