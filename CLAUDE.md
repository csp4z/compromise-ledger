# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Read first

- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) — goals, scope, constraints.
- [docs/ROADMAP.md](docs/ROADMAP.md) — the current phase and its gate. Work only on the current phase unless asked.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components and when each is introduced.
- [docs/DATA_POLICY.md](docs/DATA_POLICY.md) and [CORRECTIONS.md](CORRECTIONS.md) — hard rules on what may be collected, and how records are corrected.
- [docs/adr/](docs/adr/) — accepted decisions. Don't contradict an ADR; propose a superseding one instead.

## Hard rules

- **Open source only (OSI-approved).** Do not introduce BSL or source-available dependencies (e.g., Terraform, Vault, Redpanda, MinIO). Use OpenTofu, OpenBao, NATS or Kafka, Valkey, SeaweedFS. Check licenses before adding a dependency or image.
- **Never collect leaked data.** Crawlers parse listing metadata only and must not follow or download file links. Leak-site post URLs are stored as hashes. Leak-site claims are `claimed` until a qualifying source moves them forward. See DATA_POLICY.md.
- **Provenance is mandatory.** Every record written to silver or gold carries `Provenance`: source URL, raw document ID, crawl time, parser ID and version, confidence (0–100), and upstream license.
- **Corrections apply everywhere.** Suppressions in `silver.corrections` are applied before any gold build, API response, or export.
- **Tor crawlers** (`network="tor"`) run only in the isolated Tor runner, never in the default stack.
- **Lean first.** Do not add a component the current phase doesn't need, or before its trigger in [ADR 0002](docs/adr/0002-small-stack-and-component-triggers.md) occurs. Propose it instead, with the reason.
- **Backends behind interfaces.** Storage, transport, and search are selected by `CL_PROFILE` (`lite`, `standard`, `full`), with per-concern overrides. No backend-specific code outside its adapter.
- **No secrets or infrastructure details in Git.** No credentials, server addresses, or admin-access details. Secrets are SOPS-encrypted (age); plaintext env files stay local and are excluded by `.gitignore`.
- **Public repo.** Everything committed is public. Keep commit messages, comments, and docs about the project, not about individuals or private infrastructure.

## Architecture in one paragraph

Crawler plugins (`fetch → RawDocument`) write content-addressed blobs and a `bronze.raw_documents` Iceberg row. Parser plugins turn bronze into STIX-aligned `silver.*` tables. DuckDB SQL files in `pipelines/sql/gold/` build `gold.*`. Exporters publish Parquet/CSV/JSON plus a manifest. The API and web frontend read gold only. The lakehouse is the source of truth; everything downstream can be rebuilt. The catalog is PyIceberg `SqlCatalog` (SQLite) until ADR 0002's Lakekeeper trigger occurs.

## Conventions

- Python 3.12+, `uv` for dependency management, `ruff` for lint and format, `pytest` for tests, Pydantic v2, `httpx`. Pyright strict in `/schemas` and `/crawlers/sdk`.
- Schemas in `/schemas` are the contract between components; change them deliberately and version them. Change `/schemas` first and commit the regenerated JSON Schema. Changes must be additive (Iceberg schema evolution); renames or removals need an ADR.
- **IDs** come from `ledger_schemas.make_id()` (deterministic UUIDv5, see ADR 0004). Never use random IDs for domain objects.
- **Extend, don't modify.** New crawler = new package in `/crawlers` implementing the plugin interface, registered by entry point, with a fixture-based test that runs offline. New gold view = new SQL file. If adding one requires editing an existing component, stop and propose an interface change first.
- **No live network in tests.** To repair a broken crawler: refresh the fixture, fix the parser, add a regression test.
- **Crawler etiquette:** declare `rate_limit`, send a User-Agent with a contact address, honor robots.txt and upstream terms, and record the upstream license in `CrawlerMeta.license`.
- **Dependencies:** pin versions at least 14 days old. uv enforces this through `exclude-newer = "14 days"`, and Renovate through `minimumReleaseAge`; apply the same rule by hand to actions, hooks, and images.
- **CI/Actions:** pin actions by commit SHA; keep `permissions:` least-privilege.
- Images build for `linux/amd64` and `linux/arm64`, run as non-root, and have memory limits in Compose.
- Keep docs accurate: if a change affects setup, architecture, or the roadmap, update the relevant doc in the same change.
- **Git:** Conventional Commits, one concern per commit. While the project has a single maintainer, Claude commits directly to `main` when asked; the maintainer pushes. Revisit when there are outside contributors.

## Commands

- `make dev` — install the uv workspace and git hooks
- `make check` — everything CI runs on Python code: `make lint`, `make typecheck`, `make test`
- `make format` — apply ruff fixes and formatting
- `uv run ledger sources` · `uv run ledger crawl <id>` · `uv run ledger parse <id>` · `uv run ledger resolve` — list sources, fetch into bronze, parse the latest raw document into silver, map vendor names to `data/seeds/` (settings: `CL_*`, see docs/DEVELOPMENT.md)
- `uv run ledger build gold` · `uv run ledger export` — apply corrections and build `gold.*` from `pipelines/sql/gold/`; export rebuilds gold, then writes Parquet/CSV/JSON and `datasets.json`
- `uv run ledger check [--notify]` · `uv run ledger run daily` — health checks over `ops.crawl_runs`; the daily job runs every step, then checks and alerts
- `make schemas` — regenerate `schemas/json/` after changing a model (a test fails if it's stale)
- `make api` — serve the read-only API (FastAPI over the gold exports; docs at `/docs`)
- `make web` — build the static site into `web/build/` from the local export. In `/web`: `pnpm dev`, `pnpm check`, `pnpm build`; `CL_EXPORTS_DIR=../tests/sample-exports` builds from the committed sample. SvelteKit 3: config lives in `vite.config.ts`, and shared code is imported via `#lib/...` subpath imports with explicit `.ts` extensions (no `$lib`)
- `make sample-exports` — refresh `tests/sample-exports/` (keep it byte-exact; its checksums are tested)
- Add a dependency: `uv add --package <member> <dep>` (members: `ledger-schemas`, `ledger-crawl`, `ledger-pipelines`, `ledger-api`). Never edit `uv.lock` by hand. Web: `pnpm add -E <dep>` in `/web` (`minimumReleaseAge` enforces the 14 days).

Planned, not yet implemented (move up when they exist):

- `make up` / `make down` — the Compose stack for the current `CL_PROFILE`

## Resource awareness

Development often happens on machines with limited memory. Default to the `lite` profile for local work, and don't start services the current task doesn't need. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
