"""Fetches the KEV catalog: one JSON document, refreshed by CISA on weekdays."""

from collections.abc import Iterator
from importlib.metadata import version

from ledger_crawl import CrawlContext, CrawlerMeta, FetchedDocument, RateLimit

FEED_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


class KevCrawler:
    meta = CrawlerMeta(
        id="cisa-kev",
        version=version("ledger-crawler-cisa-kev"),
        description="CISA Known Exploited Vulnerabilities catalog (full JSON feed).",
        schedule="15 22 * * *",
        rate_limit=RateLimit(requests=1, per_seconds=10),
        # The catalog is a US government work, published by CISA under CC0 1.0.
        license="CC0-1.0",
        allowed_hosts=("www.cisa.gov",),
        content_types=("application/json",),
        max_bytes=20 * 1024 * 1024,
    )

    def fetch(self, ctx: CrawlContext) -> Iterator[FetchedDocument]:
        yield ctx.get(FEED_URL)
