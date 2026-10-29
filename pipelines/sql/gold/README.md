# Gold SQL

Each file is one DuckDB `SELECT` whose result becomes the table `gold.<name>`, and is exported as
`<name>.parquet`, `.csv`, and `.json`. Adding a gold table means adding a file here.

- **Names:** `NN_name.sql`. Files run in name order, and a file may read `silver.*`, `ops.*`, and
  any gold table from an earlier file.
- **Inputs are already corrected:** `silver.corrections` is applied before these files run, so
  suppressed records are absent and amendments are in place. Only `80_corrections_log.sql`
  reads `silver.corrections`, to publish the changelog.
- **Flat columns only** (no lists or structs), so the CSV export works. Join lists into
  `;`-separated strings.
- **Provenance:** a row-level table carries its source columns (`source_url`, `raw_document_id`,
  `crawled_at`, `parser_id`, `confidence`, `license`). An aggregate names its `sources`.
- **Deterministic output:** end with an `ORDER BY`. Timestamps are UTC.
