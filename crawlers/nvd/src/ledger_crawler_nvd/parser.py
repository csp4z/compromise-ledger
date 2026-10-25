"""Parses NVD CVE API 2.0 pages into Vulnerability records."""

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from importlib.metadata import version
from typing import Any, get_args

from ledger_crawl import ParseContext, ParserMeta
from ledger_schemas import Vulnerability
from ledger_schemas.types import CvssSeverity
from pydantic import BaseModel, ConfigDict, Field

# NVD is the reference record for CVE details; its description and scores outrank KEV's.
NVD_CONFIDENCE = 97
NVD_CWE = re.compile(r"^(CWE-\d+|NVD-CWE-Other|NVD-CWE-noinfo)$")
SKIPPED_STATUSES = {"Rejected"}


class Page(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results_per_page: int = Field(alias="resultsPerPage")
    start_index: int = Field(alias="startIndex")
    total_results: int = Field(alias="totalResults")
    vulnerabilities: list[dict[str, Any]]


def nvd_time(value: str) -> datetime:
    """NVD timestamps have no zone; the API documents them as UTC."""
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def cvss_v3(metrics: dict[str, Any]) -> tuple[float | None, CvssSeverity | None]:
    """Prefer CVSS 3.1 over 3.0, and NVD's own (Primary) score over a CNA's (Secondary)."""
    for key in ("cvssMetricV31", "cvssMetricV30"):
        entries = metrics.get(key) or []
        if entries:
            best = next((m for m in entries if m.get("type") == "Primary"), entries[0])
            data = best["cvssData"]
            severity = data.get("baseSeverity")
            if severity is not None and severity not in get_args(CvssSeverity):
                raise ValueError(f"unexpected CVSS severity {severity!r}")
            return float(data["baseScore"]), severity
    return None, None


def cwe_ids(weaknesses: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for weakness in weaknesses:
        for item in weakness.get("description", []):
            value = item.get("value", "")
            if NVD_CWE.match(value) and value not in seen:
                seen.append(value)
    return seen


def english(descriptions: list[dict[str, Any]]) -> str | None:
    return next((d["value"].strip() for d in descriptions if d.get("lang") == "en"), None) or None


class NvdParser:
    meta = ParserMeta(
        id="nvd",
        version=version("ledger-crawler-nvd"),
        source_id="nvd",
        confidence=NVD_CONFIDENCE,
        mode="incremental",
    )

    def parse(self, body: bytes, ctx: ParseContext) -> Iterator[Vulnerability]:
        page = Page.model_validate(json.loads(body))
        if page.start_index + len(page.vulnerabilities) > page.total_results:
            raise ValueError(
                f"page at {page.start_index} has {len(page.vulnerabilities)} records, "
                f"more than the {page.total_results} total"
            )
        for item in page.vulnerabilities:
            cve = item["cve"]
            if cve.get("vulnStatus") in SKIPPED_STATUSES:
                continue
            score, severity = cvss_v3(cve.get("metrics", {}))
            yield Vulnerability(
                cve_id=cve["id"],
                description=english(cve.get("descriptions", [])),
                published=nvd_time(cve["published"]),
                last_modified=nvd_time(cve["lastModified"]),
                cvss_v3_base_score=score,
                cvss_v3_severity=severity,
                cwe_ids=cwe_ids(cve.get("weaknesses", [])),
                provenance=ctx.provenance(
                    source_url=f"https://nvd.nist.gov/vuln/detail/{cve['id']}"
                ),
            )
