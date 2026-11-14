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
- Docker Compose for local and single-server runs (`lite` profile, with S3-compatible storage on the server; cut, see below: the server uses local disk).
- CI: lint, type checks, tests, gitleaks, Trivy scan, OpenSSF Scorecard, Renovate. Actions pinned by commit SHA.

**Progress (as of 2026-10-25, evening)**

Built:

- Crawler SDK (plugin contract, etiquette and data-policy enforcement, opt-in retries, snapshot and
  incremental parsers) with offline fixture tests.
- Crawlers: CISA KEV, and NVD limited to CVEs in KEV (`hasKev`). The full NVD set comes later.
- Schemas, deterministic IDs, and JSON Schema; the curated vendor list and aliases (283 vendors,
  20 security vendors by the primary-business rule); vendor resolution with the unresolved list.
- Lakehouse: Iceberg bronze/silver/gold on the SQLite catalog; DuckDB gold SQL; corrections applied
  before every gold build; Parquet/CSV/JSON exports with a checksummed `datasets.json`.
- `ledger run daily` and `ledger check`: health checks with ntfy, GitHub-issue, and
  healthchecks.io alerts. ntfy (what broke) and healthchecks.io (a dead-man's switch for a job
  that fails or never runs) are on for the server, and were verified on 2026-10-28 by making a
  step fail on purpose and recovering it (see SELF_HOSTING.md).
- Read-only FastAPI and the prerendered SvelteKit site (dashboard, data, method), both reading
  the gold exports only.
- Docker Compose `lite` stack: Caddy (HTTPS, unprivileged), the API, and the daily job, which also
  publishes the site atomically and writes backups (`ledger backup`); a run lock keeps writers
  from overlapping. [SELF_HOSTING.md](SELF_HOSTING.md) covers a Debian 13 server.
- **Live at <https://cl.kuricove.com/>** (2026-10-25), with the API at `/api` and downloads under
  `/files`. The daily job now runs on the server; the Mac schedule is retired.
- Dashboard wording reviewed (2026-10-28): KEV listing rather than "confirmed exploitation", the
  ransomware share marked as a lower bound over all entries, the time-to-KEV gap labeled
  indicative, chart notes for the backlog and partial months, and the leaderboard caveat on the
  page. Ivanti now counts as a security vendor (see `data/seeds/README.md`).

Still to do for 1a, in rough order:

1. ~~**Off-server backups:**~~ done 2026-11-11. Another machine pulls the newest nightly
   backup every day over SSH, with a key that can only fetch that file (see SELF_HOSTING.md).
   A restore was rehearsed on 2026-11-13 (see Phase 2, step 1).
2. ~~**Corrections:**~~ done and deployed 2026-10-28. Accepted requests are rows in
   `data/corrections/corrections.csv`, loaded before every gold build and checked with
   `ledger corrections`; the `corrections_log` download is the public changelog. Gold tables
   keep no history, so a removed record can't be reached through old snapshots.
3. **Small fixes:** ~~log 404s from Caddy below error level~~ (checked 2026-11-13: the
   `handle_errors` page already logs them at info), and add an `AAAA` record if the server has
   IPv6.
4. ~~**CVE denominator:**~~ built and deployed 2026-10-28. The `nvd-cve-counts`
   source counts each curated vendor's CVEs in NVD by CPE vendor name, and those of them in KEV
   (`gold.vendor_cve_counts`, `/api/v1/stats/cve-share`, a dashboard section). First local run:
   3.4% of security vendors' CVEs reached KEV, against 1.1% for the 20 other vendors with the
   most KEV entries. Caveat on the page: counts follow how each vendor assigns CVEs and how far
   NVD has assigned CPEs, and include platform matches for Microsoft, Apple, Google, and Linux.

The 7-day KEV and NVD refresh count ran on the server. Alerting was verified on 2026-10-28,
and the deploy that day included a manual run, so the count started with the scheduled run of
2026-10-29 (04:30 UTC). Every scheduled run from then through 2026-11-12 succeeded without
manual intervention, so Gate 1a closed on 2026-11-12. Item 3 is still open; it is not a gate criterion.

**Cut list if behind, in this order:** S3 storage on the server (stay on local disk) → FastAPI (ship static files and downloads only) → NVD (launch KEV-only).

**Gate 1a**

- [x] Public site live with at least one trend chart worth sharing. (<https://cl.kuricove.com/>, 2026-10-25)
- [x] Daily KEV and NVD refreshes ran for 7 consecutive days without manual intervention; alerting verified by breaking a fixture on purpose. (Scheduled runs 2026-10-29 to 2026-11-04, and every day since; alerting verified 2026-10-28.)
- [x] Data downloadable as Parquet and CSV; manifest checksums match the files. (Verified at each site build.)
- [x] A fresh clone reaches a running `lite` stack in under 10 minutes. (2026-10-25, locally: about 2 minutes to a running stack, and the site populated about 2 minutes later.)
- [x] Private corrections contact address published in [CORRECTIONS.md](../CORRECTIONS.md).

### 1b — Organizations attacked

**Deliverables**

- SEC 8-K crawler: Item 1.05 (material cybersecurity incidents) and, from the start, cyber
  incidents disclosed under Item 8.01, which most companies have used since SEC staff guidance in
  May 2024. 8.01 filings are found by text matching, so they carry lower confidence than 1.05.
  Counts describe filing behavior, not incident frequency. Requires the corrections entry path
  first, since this is the first data that names organizations.
- Organization and Incident schemas, with incident status (claimed, reported, confirmed) and a STIX extension definition for incidents.
- Incident timeline page.

**Progress (2026-10-28)**

Started before Gate 1a closes, at the maintainer's request. Deployed 2026-10-28:

- `sec-8k` crawler over EDGAR full-text search, into `silver.organizations` and
  `silver.incidents` (schema 0.7.0). Item 1.05 filings, and Item 8.01 filings found by
  disclosure phrases ("identified a cybersecurity incident", "detected unauthorized access",
  and similar) in the 8-K itself. Topic words were tried first and dropped: about 4 in 20 of
  their 8.01 matches were real disclosures, against about 16 in 20 for the phrases. 8.01
  coverage is therefore a lower bound. First backfill: 128 records from about 85 companies
  since 2023-12-18. Incidents from 8.01 filings keep the `confirmed` status for now (decided
  2026-11-01), as 1.05 incidents do; their lower confidence (75 against 90) records the difference.
  Hand check, 2026-11-12: all 35 incidents published from 8.01 filings alone (39 filings) are
  real disclosures by the company, so `confirmed` holds. Three are a vendor's breach that exposed
  the company's customer data (Phase 2: mark incidents that came through a third party). Filings
  before 2023-12-18 aren't collected, so an incident first reported earlier is dated by its first
  later filing (one case); the method page says so.
- EDGAR accepts only a `Compromise Ledger <email>` User-Agent, so crawlers can now choose that
  form (`CrawlerMeta.user_agent`).
- Suppressing an organization removes its incidents.

Also deployed 2026-10-28: `gold.incident_filings` and `gold.incidents` group a company's
filings into one incident (an amendment joins the latest incident; an original filing within 90
days of the previous one joins it), `/api/v1/incidents`, and the incident timeline page
(`/incidents`). First build: 92 incidents at 92 companies since 2023-12-18, 58 of them under
Item 1.05. The CSAF crawler moved to Phase 2 (decided 2026-11-12): it covers vendor advisories
rather than attacked organizations, and was not started. The STIX extension definition for incidents
comes with the STIX exporter (Phase 3).

**Phase gate**

- [x] Crawlers run on a schedule without manual intervention for 2 weeks. (Every scheduled
  run from 2026-10-29 through 2026-11-12 succeeded.)
- [x] README and docs accurate for a new reader. (Reviewed 2026-11-12.)

Gate 1b closed on 2026-11-12, which completes Phase 1. Phase 2 is the current phase.

## Phase 2 — Depth

**Goal:** data quality and richer exploration.

**Deliverables**

- Entity resolution for organizations, vendors, and products, beyond the curated alias table.
- LLM-assisted extraction from unstructured articles, with a labeled evaluation set built first.
- Full confidence scoring and claimed/reported/confirmed status transitions.
- Mark incidents that reached the organization through a third party (a vendor's breach), so they aren't read as attacks on its own systems.
- Dagster orchestration replacing the CLI runner. **Built 2026-11-14, not yet deployed**
  ([ADR 0007](adr/0007-dagster-trigger-after-declared-source-order.md)).
- Additional CVE sources: CVE List V5 and CISA Vulnrichment, to fill gaps in NVD enrichment.
- A generic CSAF 2.0 advisory crawler, covering many vendors through their `provider-metadata.json`
  (moved from 1b).
- Organization and vendor profile pages.
- DuckDB-WASM in-browser SQL.
- `standard` profile components (ClickHouse, NATS, Lakekeeper) and GraphQL, each added when its ADR 0002 need appears rather than by default.

**Order (accepted 2026-11-13)**

Gate work first, then sources, then the pages that use them. Sizes are rough: S is days, M a
week or two, L longer.

1. **Provenance and gate evidence (S).** Add the missing provenance columns to row-level
   exports (`incidents` lacks `crawled_at`, `vendors` lacks `confidence`, `vendor_cve_counts`
   lacks `source_url`, `confidence`, and `license`), and add a test that fails when a row-level
   gold export leaves one out. Record the evidence for failure detection. Also here: rehearse a
   restore from backup, and log Caddy's 404s below error level.
   **Done 2026-11-13.** The columns are added and the test is in place. The restore rehearsal
   unpacked the newest nightly backup into a scratch volume and rebuilt the exports: all 30
   files matched the live ones byte for byte, and `ledger check` passed. Caddy already logged
   404s at info, so it needed no change.
2. **Third-party incidents (S–M).** An additive incident field set by phrase rules plus a
   curated override list, starting from the three cases found in the 8.01 hand check. A vendor
   is named only when the company's own filing names it.
   **Done 2026-11-13, as a curated list only** (`data/seeds/third_party_incidents.csv`, schema
   0.8.0): the parser sees EDGAR search metadata, not filing text, so phrase rules would need the
   crawler to fetch each filing. Gold marks the whole incident (`via_third_party`,
   `third_party`), and the incidents page and API show it. New 8.01 incidents are checked by
   hand.
3. **CVE List V5 and CISA Vulnrichment for KEV CVEs (M).** Fills CVSS, CWE, and affected
   products where NVD lags, and gives most vulnerability facts a second source for
   corroboration scoring. Record the CVE Program's terms and attribution in the manifest.
   **Built 2026-11-13, not yet deployed** (`cve-list`, schema 0.9.0): the assigning CNA, the
   reservation date, the CNA's CVSS base score next to NVD's own, and CISA's SSVC decision
   points, on `gold.vulnerabilities`. Records come from the CVE Project's `cvelistV5`
   repository, one request per KEV CVE, then a twenty-eighth of them each day. No KEV entry
   lacked a CVSS score or CWE in NVD, so the gain is the new fields and a second source, not
   gap filling. Affected-product names are not taken yet (step 4), and corroboration scoring
   is still to do.
   Built with it, at the maintainer's request for more sources:
   - **Crawl inputs.** A crawler declares the lakehouse facts it queries by and the sources
     that run before it (`CrawlerMeta.inputs`, `after`), and can ask whether bronze already
     holds a URL (`ctx.seen`). The daily job runs sources in that order.
   - **EPSS before listing** (`epss`): each KEV CVE's exploit-prediction score on the day
     before CISA listed it.
   - **Signals** (`gold.vendor_signals`, `gold.security_vendor_signals`,
     `/api/v1/stats/signals`, a dashboard section). First local run, 2026-11-13, 1,781 KEV
     entries: 52% of security vendors' entries (81 of 156) are automatable with total
     technical impact, against 31% (500 of 1,625) for everyone else; 31% (49 of 156) had no
     EPSS score the day before listing, against 17%; of those scored, 75% (80 of 107) were
     under 0.1, against 61%. CNA and NVD base scores show no systematic gap (14 lower and 13
     higher of 54). Microsoft and Fortinet publish temporal scores in the base-score field, so
     the base score is recomputed from the vector for those.
   - **Washington breach notices** (`wa-breach-notices`, `/breaches`): 1,698 notifications
     since 2015, published as statistics only (`gold.breach_notice_yearly`,
     `gold.breach_notice_groups`). The median time from a breach starting to the organization
     becoming aware fell from over 100 days before 2021 to about a week; the median time from
     awareness to notifying the Attorney General rose from about 35 days to about 100, and 88%
     of 2023 to 2025 notices came more than 30 days after awareness.
4. **Entity resolution with a metric (M).** Link attacked organizations to vendors (both HPE and
   Microsoft appear on both sides today) and match vendor names across KEV, NVD CPEs, and CVE
   records, with the measurement described in the gate below.
5. **Vendor and organization profile pages (M).** Each organization page shows the incident
   status, the filings, the third-party mark, and the corrections link.
6. **CSAF 2.0 crawler (L).** Start with a handful of security vendors, checking each provider's
   terms; metadata and links only, never advisory text.

**Deferred until a trigger occurs**

- **Naming the organizations in breach notices:** decided 2026-11-14 to publish statistics
  only (DATA_POLICY.md). Revisit at step 5, after matching notices to SEC filers (step 4) and
  asking the Attorney General's office about reuse terms.
- **SEC company metadata** (industry code, exchange, former names, from `data.sec.gov`) for
  incidents by sector and for step 4; assessed 2026-11-13, small. It needs silver to hold
  more than one row per organization, which the incident views don't expect yet.
- **CWE names** as a seed built from MITRE's CWE download, to label weakness classes; the CWE
  API can't be crawled under the SDK's robots.txt rule (its robots.txt is unreachable).
- **HHS breach portal and CISA's Secure by Design pledge list:** assessed 2026-11-13. The
  portal has no stable structured download and names many individual practitioners; the
  pledge list has no signing dates and is only useful once vendor names resolve (step 4).
- **LLM extraction:** no free-text source exists yet, and the trigger also needs a labeled
  evaluation set.
- **Status transitions:** every current source is `confirmed`; they come with the first
  `reported` or `claimed` source. Corroboration scoring is built with step 3.
- **DuckDB-WASM:** the data is about 1 MB and already downloadable; to be dropped or kept when
  the profile pages are done.
- **ClickHouse, NATS, Lakekeeper, GraphQL:** none of their ADR 0002 needs has appeared.

**Decided 2026-11-14:** EPSS scores are redistributed with FIRST's requested attribution,
crediting Empirical Security and FIRST; breach-notice organizations are not named; publication
dates take the earlier of the CVE List's and NVD's. **Open questions:** may existing gold views
gain additive columns, or does every change need a
new view (step 1)? Should search engines index organization pages (step 5)?

**Phase gate**

- [ ] Entity resolution measurably reduces duplicates: on a frozen snapshot with a hand-labeled
  set of 100–150 name pairs checked into the tests, precision is at least 0.98 (a false merge
  misattributes an incident) and recall beats the alias table alone; distinct-entity and
  unresolved counts are published.
- [x] Every published fact carries source, crawl time, and confidence: every row-level gold
  export has a source URL, crawl time, confidence, and license, enforced by a test;
  aggregates name their `sources`. (2026-11-13: `test_every_published_fact_carries_provenance`.)
- [x] Crawler failures are detected automatically within 24 hours, per source (staleness,
  empty or failed runs, yield drops) and for the job itself (dead-man's switch). (Every source
  runs daily and `ledger check` alerts through ntfy on a failed, empty, or shrunken run;
  healthchecks.io alerts within 2 hours when the job fails or doesn't report. Both verified by
  the 2026-10-28 drill.)

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
| Domain name | Decided: `cl.kuricove.com` | — |
