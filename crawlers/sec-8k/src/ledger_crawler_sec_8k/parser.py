"""Parses EDGAR full-text search pages into ``Organization`` and ``Incident`` records.

A hit is a disclosure when:

- the filing reports Item 1.05 (material cybersecurity incident), or
- it reports Item 8.01 with nothing but 7.01 and 9.01 beside it, and the disclosure phrase the
  crawler searched for is in the 8-K itself. That leaves out phrases in exhibits (merger
  agreements, press releases) and in filings about other business, such as earnings.

Only listing metadata is kept: the company's name, CIK and tickers, and the filing's date,
form, item, and accession number. No filing text, and no names of people.
"""

import json
import re
from collections.abc import Iterator
from datetime import date
from importlib.metadata import version

from ledger_crawl import ParseContext, ParserMeta
from ledger_schemas import Incident, Organization
from ledger_schemas.types import SecItem
from pydantic import BaseModel, ConfigDict, Field

# The company's own filing: the disclosure itself is certain.
ITEM_105_CONFIDENCE = 90
# Also the company's own filing, but found by text match, so it may not describe a new incident:
# about 16 of 20 sampled matches did (2026-10-28).
ITEM_801_CONFIDENCE = 75
OTHER_EVENT_ITEMS = frozenset({"7.01", "8.01", "9.01"})
DISCLOSURE_FILES = frozenset({"8-K", "8-K/A"})
# "Astrana Health, Inc.  (ASTH)  (CIK 0001083446)"; tickers are optional.
DISPLAY_NAME = re.compile(
    r"^(?P<name>.+?)\s+(?:\((?P<tickers>[^)]*)\)\s+)?\(CIK (?P<cik>\d{10})\)$"
)


class Source(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ciks: list[str] = Field(min_length=1)
    display_names: list[str] = Field(min_length=1)
    file_date: date
    form: str
    file_type: str | None = None
    items: list[str] = Field(default_factory=list[str])
    adsh: str


class Hit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: Source = Field(alias="_source")


class Hits(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hits: list[Hit]


class Page(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hits: Hits


def disclosure_item(source: Source) -> SecItem | None:
    items = set(source.items)
    if "1.05" in items:
        return "1.05"
    if "8.01" in items and items <= OTHER_EVENT_ITEMS and source.file_type in DISCLOSURE_FILES:
        return "8.01"
    return None


def filing_url(cik: str, accession: str) -> str:
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession.replace('-', '')}/{accession}-index.htm"
    )


def filer(source: Source) -> tuple[str, str, list[str]]:
    """The first filer's CIK, name, and tickers, from its display name."""
    cik = source.ciks[0]
    for display in source.display_names:
        match = DISPLAY_NAME.match(display.strip())
        if match and match["cik"] == cik:
            tickers = [t.strip() for t in (match["tickers"] or "").split(",") if t.strip()]
            return cik, " ".join(match["name"].split()), tickers
    raise ValueError(f"no display name for CIK {cik} in {source.adsh}")


class Sec8kParser:
    meta = ParserMeta(
        id="sec-8k",
        version=version("ledger-crawler-sec-8k"),
        source_id="sec-8k",
        confidence=ITEM_105_CONFIDENCE,
        mode="incremental",
    )

    def parse(self, body: bytes, ctx: ParseContext) -> Iterator[Organization | Incident]:
        page = Page.model_validate(json.loads(body))
        for hit in page.hits.hits:
            source = hit.source
            item = disclosure_item(source)
            if item is None or source.form not in ("8-K", "8-K/A"):
                continue
            cik, name, tickers = filer(source)
            provenance = ctx.provenance(
                source_url=filing_url(cik, source.adsh),
                confidence=ITEM_105_CONFIDENCE if item == "1.05" else ITEM_801_CONFIDENCE,
            )
            organization = Organization(
                sec_cik=cik, name=name, tickers=tickers, provenance=provenance
            )
            yield organization
            yield Incident(
                organization_id=organization.id,
                # A company's own filing confirms it (DATA_POLICY.md).
                status="confirmed",
                disclosed_on=source.file_date,
                sec_accession=source.adsh,
                sec_form=source.form,  # type: ignore[arg-type]  # checked above
                sec_item=item,
                provenance=provenance,
            )
