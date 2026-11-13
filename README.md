# Compromise Ledger

An open reference dataset and analytics site tracking **organizations that have suffered cyber attacks** and **security vendors whose own products have had security flaws**.

Compromise Ledger is not a breach-data repository. It stores no leaked files or stolen data — only metadata about incidents and advisories, each linked to its public source with a confidence level.

## What it offers

Live now:

- **Security vendors' own products in CISA KEV** — a leaderboard and timeline, the share used in
  ransomware, the time from CVE publication to KEV listing, and the share of each vendor's CVEs
  that reached KEV.
- **Incidents disclosed to the SEC** — a timeline of 8-K cybersecurity filings (Items 1.05 and 8.01).
- **Open data** — every published table as Parquet, CSV, and JSON, with a checksummed manifest.
- **REST API** — read-only, with OpenAPI docs.

Planned (see the [roadmap](docs/ROADMAP.md)): more incident sources, trends by sector and threat
actor, organization and vendor profiles, STIX 2.1 bundles, and a TAXII 2.1 feed.

## Principles

- **Provenance on everything.** Every fact links to its source, crawl time, and confidence score.
- **Claimed vs. confirmed.** Leak-site claims are labeled as claims until corroborated.
- **Correctable.** Anyone can request a correction or takedown through a [published process](CORRECTIONS.md).
- **Open source throughout.** Every component in the stack is OSI-licensed.
- **Standards-based.** The data model follows STIX 2.1.
- **Lean first.** A component is added only when a real need requires it, and the reason is recorded in an [ADR](docs/adr/).

## Documentation

| Doc | What's in it |
| --- | --- |
| [Project brief](docs/PROJECT_BRIEF.md) | Why this exists, scope, and constraints |
| [Architecture](docs/ARCHITECTURE.md) | Every component: what it does, can do, and why it's there |
| [Roadmap](docs/ROADMAP.md) | Phases, deliverables, and phase gates |
| [Development](docs/DEVELOPMENT.md) | Runtime profiles and environment setup |
| [Self-hosting](docs/SELF_HOSTING.md) | Running the stack on a server, with backups and alerts |
| [Data policy](docs/DATA_POLICY.md) | What we collect, what we never collect, claim status |
| [Corrections](CORRECTIONS.md) | How to request a correction or takedown, and response targets |
| [Decision records](docs/adr/) | Why the architecture looks the way it does |
| [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) | How to contribute; how to report a vulnerability |

## Status

Phase 1a (CISA KEV and NVD, through the lens of security vendors' own products) is live at <https://cl.kuricove.com/>, with the API at `/api` and downloads under `/files`. Phase 1b (organizations attacked) added SEC 8-K incident filings. Phase 1 is complete, and Phase 2 (data quality and depth) is next. See the [roadmap](docs/ROADMAP.md).

## License

- **Code:** [Apache License 2.0](LICENSE)
- **Data** (published exports and `data/seeds/`): [Creative Commons Attribution 4.0](LICENSE-DATA). Upstream sources keep their own terms, which are recorded in each record's provenance.
