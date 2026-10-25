"""Fetches NVD CVE records for the CVEs in CISA KEV (CVE API 2.0, ``hasKev``).

The first run fetches the whole KEV set. Later runs fetch what changed since the previous good
run: records modified in the window, and CVEs added to KEV in the window.
"""

import json
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from importlib.metadata import version

from ledger_crawl import CrawlContext, CrawlerMeta, FetchedDocument, RateLimit

API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
# NVD allows 2000, but streams at tens of KB/s and drops large responses: 100 records took
# 16 s, 500 took over 3 minutes before the connection was reset (measured 2026-10-25).
PAGE_SIZE = 100
MAX_WINDOW = timedelta(days=120)  # NVD rejects longer date ranges
OVERLAP = timedelta(hours=1)  # re-read the window's edge; duplicates are harmless
NVD_NOTICE = "This product uses data from the NVD API but is not endorsed or certified by the NVD."


def nvd_date(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")


class NvdCrawler:
    meta = CrawlerMeta(
        id="nvd",
        version=version("ledger-crawler-nvd"),
        description="NIST National Vulnerability Database: CVE records for CVEs in CISA KEV.",
        schedule="30 21 * * *",
        # NVD's public limit without an API key: 5 requests per rolling 30 seconds.
        rate_limit=RateLimit(requests=5, per_seconds=30),
        # NVD data is a US government work; its terms ask for the notice below.
        license="LicenseRef-NVD-Terms-of-Use",
        attribution=NVD_NOTICE,
        allowed_hosts=("services.nvd.nist.gov",),
        content_types=("application/json",),
        max_bytes=64 * 1024 * 1024,
        retries=3,
    )

    def fetch(self, ctx: CrawlContext) -> Iterator[FetchedDocument]:
        end = ctx.now()
        start = ctx.last_success - OVERLAP if ctx.last_success else None
        if start is None or end - start > MAX_WINDOW:
            yield from self._pages(ctx, {})
            return
        window_start, window_end = nvd_date(start), nvd_date(end)
        yield from self._pages(
            ctx, {"lastModStartDate": window_start, "lastModEndDate": window_end}
        )
        yield from self._pages(ctx, {"kevStartDate": window_start, "kevEndDate": window_end})

    def _pages(self, ctx: CrawlContext, filters: Mapping[str, str]) -> Iterator[FetchedDocument]:
        start_index = 0
        while True:
            params = {
                "hasKev": "",
                **filters,
                "resultsPerPage": PAGE_SIZE,
                "startIndex": start_index,
            }
            doc = ctx.get(API_URL, params=params)
            yield doc
            # Reading the totals to page is the only parsing a crawler does.
            page = json.loads(doc.body)
            start_index += page["resultsPerPage"]
            if page["resultsPerPage"] == 0 or start_index >= page["totalResults"]:
                return
