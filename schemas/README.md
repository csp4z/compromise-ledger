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
| `Correction` | `silver.corrections` | `x-ledger-correction` | `request_ref`, `target_id`, `amend_field` (if set) |

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

## Changing a schema

1. Edit the model. Changes must be additive (new optional fields, new vocabulary values).
   Renames, removals, and type changes need an ADR.
2. Bump `SCHEMA_VERSION` in `ledger_schemas/__init__.py` (minor for additive changes).
3. Run `make schemas` and commit the regenerated `json/` files with the change. A test fails if
   they are stale.
