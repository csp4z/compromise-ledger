# ADR 0007: Dagster runs the daily pipeline

- **Status:** Accepted
- **Date:** 2026-11-14
- **Trigger:** [ADR 0002](0002-small-stack-and-component-triggers.md), Dagster row

## Context

ADR 0002 allows Dagster in Phase 2 once there are "more than 5 sources, or cross-source
dependencies or backfills become painful through the CLI". Phase 2 is current, and the first half
has occurred:

- There are seven sources: `cisa-kev`, `nvd`, `nvd-cve-counts`, `sec-8k`, `wa-breach-notices`,
  `cve-list`, and `epss`.
- Two of them depend on another. `cve-list` and `epss` are fetched once per CVE in KEV, so
  `cisa-kev` must be crawled and parsed first. Crawlers declare this in `CrawlerMeta.after`.

The plain runner copes: `ledger run daily` orders sources from those declarations. Waiting for it
to hurt was considered (an earlier draft of this ADR proposed replacing the source count with
that), and the maintainer chose to add Dagster now, for what it shows: an asset graph with the
dependencies, run history, per-source health as asset checks, and a UI to re-run one source.

Memory was measured before deciding (2026-11-14):

- The public server has 8 GB. The stack's Compose limits added up to about 1.9 GB, and the host
  used about 0.9 GB with 6.9 GB available. The daily job peaked at 820 MB.
- Dagster 1.13 (Apache-2.0; its 47 new dependencies are all OSI-licensed), run locally with this
  pipeline's code: the webserver, daemon, and code server took about 380 MB together when idle,
  and a run worker adds about 150–250 MB while a job runs.

## Decision

- **Dagster runs the daily pipeline on the server.** The definitions live in a new workspace
  package, `orchestration/` (`ledger-orchestration`). Each step is the function the CLI already
  calls; Dagster arranges them as assets: one per source (after the sources it names in
  `after`), then vendor resolution, exports, the site, maintenance, backup, and health.
- **Behavior is kept from the CLI.** A failing step records its failure instead of raising, so
  the rest still run on the last good data. Each source carries a `healthy` asset check from
  `ledger check`; the `health` asset runs every check, sends the same alerts (ntfy, GitHub
  issue, healthchecks.io), and fails the run if anything broke. A run-failure sensor alerts when
  a run dies before reaching `health`.
- **One writer.** The run holds the ledger lock and uses Dagster's in-process executor, and the
  instance runs one job at a time. Run history is SQLite in a Docker volume; no database server.
- **Two services replace the supercronic job.** `dagster-daemon` runs the schedule (04:30 UTC),
  the sensor, and the runs, with a 2 GB limit. `dagster-webserver` serves the UI with a 768 MB
  limit, bound to the host's loopback: Dagster's open-source UI has no authentication, so it is
  reached through an SSH tunnel, never through Caddy.
- **The CLI stays.** `ledger run daily` and the supercronic `job` service (Compose profile
  `cron`) remain as the fallback and for running without Dagster on a laptop.
- `CL_PROFILE` is unchanged: the server still runs `lite` storage and catalog. Orchestration is
  chosen by which Compose services run, not by the profile.

## Consequences

- Memory limits on the server go from about 1.9 GB to about 3.2 GB of 7.7 GB. Expected use is
  about 1.5 GB during a run.
- The job image grows by Dagster and its dependencies; the API image carries them too, since it
  installs the whole workspace.
- Two more long-running containers to update. Renovate covers the Python packages.
- Run history and asset metadata live in the `dagster` volume. Losing it loses history only:
  the data is in the lakehouse, which the backup covers.
- Adding a source still needs no orchestration change: its asset and dependencies come from
  `CrawlerMeta`.
