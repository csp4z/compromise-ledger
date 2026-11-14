"""Crawl inputs: facts the lakehouse already holds that a crawler may ask for.

Some sources are queried per item: NVD once per curated vendor, the CVE List once per CVE in
KEV. A crawler names what it needs in ``CrawlerMeta.inputs``, the runner fills exactly those,
and the crawler reads them from its ``CrawlContext``. Crawlers never read the lakehouse
themselves, so the context stays the only way they touch anything outside their own code.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

InputName = Literal["cpe_vendors", "kev_cves"]


@dataclass(frozen=True, slots=True)
class KevCve:
    """A CVE in CISA KEV and the day CISA added it."""

    cve_id: str
    date_added: date


@dataclass(frozen=True, slots=True)
class CrawlInputs:
    """One field per ``InputName``. The runner leaves the ones a crawler didn't ask for empty."""

    cpe_vendors: tuple[str, ...] = ()
    kev_cves: tuple[KevCve, ...] = ()


class UndeclaredInputError(LookupError):
    """A crawler read an input it doesn't list in ``CrawlerMeta.inputs``."""
