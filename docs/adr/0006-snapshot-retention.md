# ADR 0006: Seven days of table history

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

ADR 0003 chose Iceberg partly for snapshots and time travel, but set no limit on how long
snapshots are kept. After two weeks on the server, nothing had been expired:

- Each daily parse replaces a source's silver rows, so every day adds a new copy of the silver
  data files while the old ones stay referenced by older snapshots.
- Each commit writes a new `metadata.json` that lists every snapshot so far, and the old files
  are kept. `ops.crawl_runs` takes several commits a day, so its metadata grows quadratically.

The nightly backup grew from 13.5 MB to 26 MB in ten days, mostly from silver copies and
`ops.crawl_runs` metadata, and the growth accelerates.

Table history is not the record of "what did we know, when". Bronze is: every raw document is
kept with its fetch time and content hash, and silver and gold can be rebuilt from it.

## Decision

- Bronze, silver, and ops tables keep **7 days** of snapshots. `ledger maintain` expires older
  snapshots, always keeping the current one, and deletes the manifest lists, manifests, and data
  files that no remaining snapshot uses. The daily job runs it after publishing the site and
  before the backup.
- Every table keeps at most 10 previous `metadata.json` files
  (`write.metadata.delete-after-commit.enabled`, `write.metadata.previous-versions-max`).
- Gold is unchanged: it is purged and rebuilt on every run and keeps no history.
- Raw blobs are never expired. They are the provenance trail.

## Consequences

- Backups stay roughly proportional to the data, plus one week of changes.
- Time travel on silver reaches back a week, which is enough to debug a bad parse. Older
  states are rebuilt from bronze.
- A corrected record also leaves silver's history after 7 days. Silver itself still holds the
  original row, as `CORRECTIONS.md` describes.
- PyIceberg expires snapshots but doesn't delete their files, so the adapter does that itself.
  If deletion fails part way, the leftover files are unreferenced and harmless; nothing finds
  them again, so a later orphan-file sweep may be needed if that happens. The same applies to
  the `metadata.json` files that dropped out of Iceberg's metadata log before this setting
  existed (about 0.6 MB of the backup); they are left in place.
