"""Searches EDGAR full-text search for 8-K and 8-K/A filings that may disclose a cybersecurity
incident, by the phrases companies use to disclose one.

Each phrase is searched per form (EDGAR reads a list of forms as the last one only), over a date
window: since Item 1.05 took effect on the first run, then since the previous good run. The
parser decides which hits are disclosures; the crawler only fetches the result pages.
"""

import json
from collections.abc import Iterator
from datetime import date, timedelta
from importlib.metadata import version

from ledger_crawl import CrawlContext, CrawlerMeta, FetchedDocument, RateLimit
from ledger_schemas.types import SecForm

SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
# Item 1.05 applied to most registrants from this date.
RULE_START = date(2023, 12, 18)
# "Item 1.05" finds material-incident filings by their heading. The others are the language of
# an actual disclosure under Item 8.01, where most companies have filed since May 2024. Topic
# words ("cybersecurity incident", "cyberattack", "ransomware") are not used: they mostly match
# forward-looking-statement boilerplate (measured 2026-10-28: 4 real disclosures in a sample of
# 20 such matches, against about 16 of 20 for these phrases).
PHRASES = (
    '"Item 1.05"',
    '"identified a cybersecurity incident"',
    '"detected a cybersecurity incident"',
    '"experienced a cybersecurity incident"',
    '"became aware of a cybersecurity incident"',
    '"identified unauthorized access"',
    '"detected unauthorized access"',
    '"unauthorized third party gained access"',
    '"identified unauthorized activity"',
    '"detected unauthorized activity"',
    '"learned of unauthorized activity"',
)
FORMS: tuple[SecForm, ...] = ("8-K", "8-K/A")
# Filings can appear in the index a day or two after their filing date.
OVERLAP = timedelta(days=3)
MAX_RESULTS = 10_000  # EDGAR search can't page past this


def search_params(
    phrase: str, form: SecForm, start: date, end: date, offset: int
) -> dict[str, str | int]:
    return {
        "q": phrase,
        "forms": form,
        "dateRange": "custom",
        "startdt": start.isoformat(),
        "enddt": end.isoformat(),
        "from": offset,
    }


class Sec8kCrawler:
    meta = CrawlerMeta(
        id="sec-8k",
        version=version("ledger-crawler-sec-8k"),
        description=(
            "SEC EDGAR full-text search: cybersecurity incidents disclosed in Form 8-K "
            "(Item 1.05, and Item 8.01 by disclosure phrases)."
        ),
        schedule="0 23 * * *",
        # SEC fair access allows 10 requests per second; this stays far below it.
        rate_limit=RateLimit(requests=1, per_seconds=2),
        # EDGAR filings are US government public records.
        license="LicenseRef-SEC-EDGAR-Public-Record",
        allowed_hosts=("efts.sec.gov",),
        content_types=("application/json",),
        max_bytes=8 * 1024 * 1024,
        retries=3,
        # EDGAR refuses any User-Agent but "<name> <email>" as an undeclared automated tool.
        user_agent="name-email",
    )

    def fetch(self, ctx: CrawlContext) -> Iterator[FetchedDocument]:
        start = (ctx.last_success - OVERLAP).date() if ctx.last_success else RULE_START
        end = ctx.now().date()
        for phrase in PHRASES:
            for form in FORMS:
                yield from self._pages(ctx, phrase, form, start, end)

    def _pages(
        self, ctx: CrawlContext, phrase: str, form: SecForm, start: date, end: date
    ) -> Iterator[FetchedDocument]:
        offset = 0
        while True:
            doc = ctx.get(SEARCH_URL, params=search_params(phrase, form, start, end, offset))
            yield doc
            # Reading the totals to page is the only parsing a crawler does.
            hits = json.loads(doc.body)["hits"]
            total = hits["total"]["value"]
            if total > MAX_RESULTS:
                raise ValueError(f"{phrase} in {form}: {total} hits, more than search can page")
            offset += len(hits["hits"])
            if not hits["hits"] or offset >= total:
                return
