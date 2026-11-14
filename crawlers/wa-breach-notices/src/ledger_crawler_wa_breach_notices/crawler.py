"""Fetches the Washington Attorney General's breach-notification dataset from data.wa.gov.

Washington requires an organization to notify the Attorney General when a breach involves more
than 500 residents. The office publishes one row per notice: the notifier's name, the dates it
reports (breach start and end, when it became aware, when it notified), the cause, and the
number of residents. The whole dataset is one request, a few thousand rows.
"""

from collections.abc import Iterator
from importlib.metadata import version

import httpx
from ledger_crawl import CrawlContext, CrawlerMeta, FetchedDocument, RateLimit

DATASET_URL = "https://data.wa.gov/resource/sb4j-ca4h.json"
# Far above the dataset's size (about 1,700 rows after ten years); the parser fails if a page
# ever comes back full, since that would mean rows were cut off.
LIMIT = 50_000
PARAMS: dict[str, str | int] = {"$limit": LIMIT, "$order": "id"}
WA_NOTICE = (
    "Data Breach Notifications Affecting Washington Residents, Washington State Attorney "
    "General's Office, Consumer Protection Division (https://data.wa.gov/d/sb4j-ca4h)."
)


def url() -> str:
    return str(httpx.URL(DATASET_URL, params=PARAMS))


class WaBreachNoticeCrawler:
    meta = CrawlerMeta(
        id="wa-breach-notices",
        version=version("ledger-crawler-wa-breach-notices"),
        description=(
            "Washington State Attorney General: data-breach notifications affecting more "
            "than 500 Washington residents (dates, cause, industry, residents affected)."
        ),
        schedule="10 23 * * *",
        # robots.txt asks for a one-second crawl delay; this is one request a day.
        rate_limit=RateLimit(requests=1, per_seconds=10),
        # The dataset states no license. It is a public record the office publishes as open
        # data, with the attribution below. See DATA_POLICY.md for what is published from it.
        license="LicenseRef-WA-AGO-No-Stated-License",
        attribution=WA_NOTICE,
        allowed_hosts=("data.wa.gov",),
        content_types=("application/json",),
        max_bytes=32 * 1024 * 1024,
        retries=2,
    )

    def fetch(self, ctx: CrawlContext) -> Iterator[FetchedDocument]:
        yield ctx.get(DATASET_URL, params=PARAMS)
