"""Parses the KEV feed into Vulnerability and ProductMention records."""

import json
import unicodedata
from collections.abc import Iterator
from datetime import date
from importlib.metadata import version
from typing import Literal

from ledger_crawl import ParseContext, ParserMeta
from ledger_schemas import ProductMention, Vulnerability
from pydantic import BaseModel, ConfigDict, Field

# A KEV listing is CISA's confirmation of exploitation in the wild.
KEV_CONFIDENCE = 95


class KevEntry(BaseModel):
    # Upstream adds fields over time (e.g. forensicTriage); ignore what we don't map yet.
    model_config = ConfigDict(extra="ignore")

    cve_id: str = Field(alias="cveID")
    vendor_project: str = Field(alias="vendorProject")
    product: str
    date_added: date = Field(alias="dateAdded")
    short_description: str = Field(alias="shortDescription")
    due_date: date = Field(alias="dueDate")
    ransomware_use: Literal["Known", "Unknown"] = Field(alias="knownRansomwareCampaignUse")
    cwes: list[str] = Field(default_factory=list[str])


class KevFeed(BaseModel):
    model_config = ConfigDict(extra="ignore")

    catalog_version: str = Field(alias="catalogVersion")
    count: int
    vulnerabilities: list[KevEntry]


def clean_name(name: str) -> str:
    """NFKC-normalize and collapse whitespace; upstream names have stray and non-ASCII spaces."""
    return " ".join(unicodedata.normalize("NFKC", name).split())


class KevParser:
    meta = ParserMeta(
        id="cisa-kev",
        version=version("ledger-crawler-cisa-kev"),
        source_id="cisa-kev",
        confidence=KEV_CONFIDENCE,
    )

    def parse(self, body: bytes, ctx: ParseContext) -> Iterator[Vulnerability | ProductMention]:
        feed = KevFeed.model_validate(json.loads(body))
        if feed.count != len(feed.vulnerabilities):
            raise ValueError(
                f"catalog {feed.catalog_version} declares {feed.count} entries, "
                f"has {len(feed.vulnerabilities)}"
            )
        provenance = ctx.provenance()
        for entry in feed.vulnerabilities:
            vuln = Vulnerability(
                cve_id=entry.cve_id,
                description=entry.short_description.strip() or None,
                cwe_ids=entry.cwes,
                kev_date_added=entry.date_added,
                kev_due_date=entry.due_date,
                kev_ransomware_use="known" if entry.ransomware_use == "Known" else "unknown",
                provenance=provenance,
            )
            yield vuln
            yield ProductMention(
                vulnerability_id=vuln.id,
                vendor_name=clean_name(entry.vendor_project),
                product_name=clean_name(entry.product),
                provenance=provenance,
            )
