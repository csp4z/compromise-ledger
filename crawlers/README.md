# Crawlers

Each source is its own package in this directory, built on the SDK in [`sdk/`](sdk/)
(`ledger-crawl`). A source package provides two plugins:

- a **crawler** that fetches documents, which the runner stores as content-addressed blobs and
  `bronze.raw_documents` rows;
- a **parser** that turns one stored document into silver records (`ledger_schemas` models).

Crawling and parsing are separate, so a parser fix is replayed from bronze without re-crawling.

## Writing a crawler

1. Create `crawlers/<source-id>/` as a uv workspace member, depending on `ledger-crawl`.
2. Declare a `CrawlerMeta`: ID, version, cron schedule (UTC), rate limit, upstream license
   (SPDX), the exact hosts it may contact, accepted content types, and a size cap.
3. Implement `fetch(ctx)`, yielding `ctx.get(...)` results. Use `ctx.last_success` for incremental
   crawls. Don't parse here.
4. Declare a `ParserMeta` (ID, version, source ID, default confidence) and implement
   `parse(body, ctx)`, attaching `ctx.provenance()` to every record.
5. Register both in `pyproject.toml`; the entry point name must equal the plugin's `meta.id`:

   ```toml
   [project.entry-points."ledger.crawlers"]
   example = "ledger_crawler_example:ExampleCrawler"

   [project.entry-points."ledger.parsers"]
   example = "ledger_crawler_example:ExampleParser"
   ```

6. Record real responses in `fixtures/` and test both plugins offline with
   `ledger_crawl.testing.offline_context` and `Fixture`. Any request without a fixture fails the
   test.

## What the SDK enforces

All network access goes through `CrawlContext`, so these hold for every crawler:

| Rule | How |
|---|---|
| Rate limit | Requests are spaced to `rate_limit`. |
| Identification | User-Agent `compromise-ledger/<version> (+<repo URL>; <contact>)`. The contact address is runtime configuration and is never committed. |
| robots.txt | Checked once per host. Per RFC 9309, a 4xx means no restrictions, and a 5xx or unreachable file means disallow everything. |
| Host allowlist | HTTPS only, to `allowed_hosts`, redirects included. A link off the allowlist can't be followed. |
| No file downloads | Only the declared `content_types` are accepted, and bodies over `max_bytes` are aborted mid-stream. |
| IDs | The raw document ID is the SHA-256 of the body, computed by the SDK. |
| Tor isolation | `discover_crawlers()` returns clearnet crawlers only; Tor crawlers load only when the isolated Tor runner asks for them. |

Errors (`ledger_crawl.errors`) propagate out of `fetch`, and the run is recorded as failed.
