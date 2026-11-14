"""Parses EPSS API pages into ``EpssScore`` records.

A CVE the page leaves out had no score that day: EPSS scores published CVEs only, so a flaw
exploited before its CVE was public has no score on the day before its KEV listing.
"""

import json
from collections.abc import Iterator
from datetime import date
from importlib.metadata import version

from ledger_crawl import ParseContext, ParserMeta
from ledger_schemas import EpssScore, make_id
from pydantic import BaseModel, ConfigDict

# What FIRST published for that CVE and day is a matter of record. The score itself is a
# model's estimate, which is what the field means.
EPSS_CONFIDENCE = 95


class Score(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cve: str
    epss: float
    percentile: float
    date: date


class Page(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    total: int
    data: list[Score]


class EpssParser:
    meta = ParserMeta(
        id="epss",
        version=version("ledger-crawler-epss"),
        source_id="epss",
        confidence=EPSS_CONFIDENCE,
        mode="incremental",
    )

    def parse(self, body: bytes, ctx: ParseContext) -> Iterator[EpssScore]:
        page = Page.model_validate(json.loads(body))
        if page.status != "OK":
            raise ValueError(f"EPSS answered {page.status!r}")
        if page.total != len(page.data):
            raise ValueError(f"page has {len(page.data)} of {page.total} scores; it was cut short")
        for score in page.data:
            yield EpssScore(
                vulnerability_id=make_id("vulnerability", score.cve),
                cve_id=score.cve,
                score_date=score.date,
                epss=score.epss,
                percentile=score.percentile,
                provenance=ctx.provenance(),
            )
