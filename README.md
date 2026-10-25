# Compromise Ledger

An open reference dataset and analytics site tracking **organizations that have suffered cyber attacks** and **security vendors whose own products have had security flaws**.

Compromise Ledger is not a breach-data repository. It stores no leaked files or stolen data — only metadata about incidents and advisories, each linked to its public source with a confidence level.

## What it offers

- **Trends and visualizations** — incidents over time, by sector, by threat actor, and by vendor.
- **Organization and vendor profiles** — incident timelines and product advisories in one place.
- **Open data** — the full normalized dataset as Parquet, CSV, and JSON, with STIX 2.1 bundles to follow.
- **APIs** — REST with OpenAPI docs; GraphQL and a TAXII 2.1 feed for threat-intel platforms are planned.

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
| [Data policy](docs/DATA_POLICY.md) | What we collect, what we never collect, claim status |
| [Corrections](CORRECTIONS.md) | How to request a correction or takedown, and response targets |
| [Decision records](docs/adr/) | Why the architecture looks the way it does |
| [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) | How to contribute; how to report a vulnerability |

## Status

Early development. Phase 1a (CISA KEV and NVD, through the lens of security vendors' own products) is under construction, and nothing is published yet. See the [roadmap](docs/ROADMAP.md).

## License

- **Code:** [Apache License 2.0](LICENSE)
- **Data** (published exports and `data/seeds/`): [Creative Commons Attribution 4.0](LICENSE-DATA). Upstream sources keep their own terms, which are recorded in each record's provenance.
