# ledger-schemas

The data contract shared by crawlers, pipelines, the API, and exports. Models are Pydantic v2;
the JSON Schema files in [`json/`](json/) are generated from them and committed.

## Models

| Model | Table | STIX type | Natural key (→ ID) |
|---|---|---|---|
| `RawDocument` | `bronze.raw_documents` | — | SHA-256 of the body (not a STIX ID) |
| `Vendor` | `silver.vendors` | `identity` | `slug` |
| `Product` | `silver.products` | `software` | `vendor_id`, `slug` |
| `Vulnerability` | `silver.vulnerabilities` | `vulnerability` | `cve_id` |
| `Relationship` | `silver.relationships` | `relationship` | `relationship_type`, `source_ref`, `target_ref` |
| `ProductMention` | `silver.product_mentions` | `x-ledger-product-mention` | `vulnerability_id`, SHA-256 of the vendor and product names |
| `CveCount` | `silver.cve_counts` | `x-ledger-cve-count` | `cpe_vendor`, `scope` |
| `Organization` | `silver.organizations` | `identity` | `"sec-cik"`, `sec_cik` |
| `Incident` | `silver.incidents` | `incident` | `"sec"`, `sec_accession` |
| `Correction` | `silver.corrections` | `x-ledger-correction` | `request_ref`, `target_id`, `amend_field` (if set) |
| `CrawlRun` | `ops.crawl_runs` | — | `run_id` (operational, not a STIX ID) |
| `UnresolvedVendorName` | `ops.unresolved_vendor_names` | — | `vendor_name` (rebuilt on every resolution) |

`Provenance` is a struct embedded in every silver model. Corrections are the exception: they are
maintainer decisions rather than parsed source data, and carry `request_ref` and `decided_at`
instead.

## IDs

IDs are `<stix-type>--<uuid5>`, from `make_id(stix_type, *key_parts)` (see
[ADR 0004](../docs/adr/0004-stix-aligned-columnar-model.md)). The UUID name is the type and the key
parts joined by `|`, under a fixed project namespace. Models derive `id` when it is omitted and
reject a supplied `id` that doesn't match, so a record can't carry a random or stale ID.

Key fields are used verbatim, never normalized, so their formats are strict: slugs are
lower-case and hyphenated, CVE IDs upper-case. A slug must never change once published. Renames
go through the vendor alias table instead.

## Conventions

- Datetimes must be timezone-aware and are stored in UTC.
- Unknown fields are rejected (`extra="forbid"`), and instances are immutable.
- A vulnerability gets one silver row per source; each fills only the fields it knows. Gold
  merges them.
- Parsers don't resolve entities. A source's free-text vendor and product names become
  `ProductMention` rows. A resolution step maps them through the alias table in `data/seeds/`
  to `Vendor`, `Product`, and `has` relationships, and publishes the names it can't resolve.

## Planned: flaws and incidents without a CVE

Phase 1a sources (KEV, NVD) always have a CVE, so `Vulnerability` is keyed by `cve_id` for now.
Later sources won't: vendor advisories without a CVE, and flaws reported by researchers or the
media that the vendor never acknowledged. When the first such source is added, these changes
come with it, all of them additive:

- `cve_id` becomes optional, and records without one are keyed by another identifier: a vendor
  advisory ID, a GHSA ID, or a project-assigned key for media reports. These formats can't
  collide with CVE IDs, so existing IDs are unaffected.
- When a CVE is assigned later, the two records are linked with a STIX `duplicate-of`
  relationship and merged in gold.
- Vulnerabilities get the same `claimed` / `reported` / `confirmed` status as incidents
  (see [DATA_POLICY.md](../docs/DATA_POLICY.md#claims-vs-confirmed-facts)): a media report alone
  is `reported`; a vendor advisory, CVE, or KEV entry is `confirmed`.
- A vendor that was itself breached is an `Incident` with the vendor as the victim
  organization, not a `Vulnerability`.

## Changing a schema

1. Edit the model. Changes must be additive (new optional fields, new vocabulary values).
   Renames, removals, and type changes need an ADR.
2. Bump `SCHEMA_VERSION` in `ledger_schemas/__init__.py` (minor for additive changes).
3. Run `make schemas` and commit the regenerated `json/` files with the change. A test fails if
   they are stale.
