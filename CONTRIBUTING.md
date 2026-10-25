# Contributing

Thanks for your interest. The project is at an early stage, and its conventions are being set now.

## Ground rules

- **Open source only.** New dependencies, images, and tools must be OSI-licensed. No BSL or
  source-available licenses. Name the license in your PR description.
- **Data ethics.** Contributions must never add leaked files, dumps, or links to them. Every new
  fact must carry provenance. See the [data policy](docs/DATA_POLICY.md), and
  [CORRECTIONS.md](CORRECTIONS.md) for how records are corrected.
- **Current phase only.** Work is scoped to the current phase in the [roadmap](docs/ROADMAP.md).
- **Small stack.** Proposals for a new service or framework need an ADR in [docs/adr/](docs/adr/)
  that names the concrete need. See [ADR 0002](docs/adr/0002-small-stack-and-component-triggers.md).

## Workflow

1. Open an issue first for anything bigger than a small fix.
2. Keep PRs small, with one concern each.
3. Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`,
   `chore:` …).
4. Run `pre-commit install` once. Hooks run ruff, gitleaks, and basic file checks.
5. CI must be green before review.

## Adding a data source

Sources are plugins: each crawler is its own package in `/crawlers`, registered through a Python
entry point. Adding one should not require editing existing crawlers or pipelines. If it does,
open an issue to discuss the interface first. The step-by-step guide is in
[crawlers/README.md](crawlers/README.md). Every source must:

- declare its rate limit and schedule, and send a User-Agent with a contact address;
- honor robots.txt and the source's terms of use, and record its license;
- ship recorded fixtures so its parser can be tested without network access.

## Contributing data

Curated seed data (for example the security-vendor list and vendor aliases in `data/seeds/`) is
changed through PRs. Cite a source for each addition; see [data/seeds/README.md](data/seeds/README.md)
for the format and for who counts as a security vendor. Seed data is licensed CC BY 4.0, like the
rest of the published dataset.

## Licensing of contributions

By submitting a contribution you agree that it is licensed under the
[Apache License 2.0](LICENSE) (code) or [CC BY 4.0](LICENSE-DATA) (data), as described in the
README.
