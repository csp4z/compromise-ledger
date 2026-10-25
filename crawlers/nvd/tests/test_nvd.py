import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from ledger_crawl import ParseContext
from ledger_crawl.registry import discover_crawlers, discover_parsers
from ledger_crawl.testing import FIXED_NOW, Fixture, offline_context
from ledger_crawler_nvd import API_URL, NvdCrawler, NvdParser
from ledger_crawler_nvd.crawler import OVERLAP, PAGE_SIZE, nvd_date
from ledger_crawler_nvd.parser import NVD_CONFIDENCE, cvss_v3
from ledger_schemas import Vulnerability, make_id

FIXTURES = Path(__file__).parents[1] / "fixtures"


def url(start: int, **filters: str) -> str:
    """The URL the crawler requests, with its parameter order."""
    params = {"hasKev": "", **filters, "resultsPerPage": PAGE_SIZE, "startIndex": start}
    return str(httpx.URL(API_URL, params=params))


def full_fetch_routes() -> dict[str, Fixture]:
    return {
        url(0): Fixture(FIXTURES / "page-0.json"),
        url(3): Fixture(FIXTURES / "page-1.json"),
    }


def crawl(routes: dict[str, Fixture], last_success: datetime | None = None) -> list[Any]:
    crawler = NvdCrawler()
    with offline_context(crawler.meta, routes, last_success=last_success) as ctx:
        return list(crawler.fetch(ctx))


def parse_body(body: bytes) -> list[Vulnerability]:
    (doc,) = crawl({url(0): Fixture(body)})
    ctx = ParseContext(NvdParser.meta, doc.raw, NvdCrawler.meta.license)
    return list(NvdParser().parse(doc.body, ctx))


def page_with(edit: Any) -> bytes:
    page = json.loads((FIXTURES / "page-0.json").read_bytes())
    edit(page["vulnerabilities"][0]["cve"])
    page["vulnerabilities"] = page["vulnerabilities"][:1]
    page["totalResults"] = page["resultsPerPage"] = 1
    return json.dumps(page).encode()


def test_first_run_pages_through_the_kev_set() -> None:
    docs = crawl(full_fetch_routes())
    assert len(docs) == 2
    assert all(d.raw.source_id == "nvd" for d in docs)


def test_later_runs_fetch_the_changed_window() -> None:
    last = FIXED_NOW - timedelta(days=1)
    window = {"Start": nvd_date(last - OVERLAP), "End": nvd_date(FIXED_NOW)}
    empty = Fixture(FIXTURES / "empty.json")
    routes = {
        url(0, lastModStartDate=window["Start"], lastModEndDate=window["End"]): empty,
        url(0, kevStartDate=window["Start"], kevEndDate=window["End"]): empty,
    }
    assert len(crawl(routes, last_success=last)) == 2
    assert nvd_date(FIXED_NOW) == "2026-01-01T00:00:00.000+00:00"


def test_long_gap_falls_back_to_a_full_fetch() -> None:
    assert len(crawl(full_fetch_routes(), last_success=FIXED_NOW - timedelta(days=200))) == 2


def test_parses_real_records() -> None:
    docs = crawl(full_fetch_routes())
    records = []
    for doc in docs:
        ctx = ParseContext(NvdParser.meta, doc.raw, NvdCrawler.meta.license)
        records += list(NvdParser().parse(doc.body, ctx))
    by_cve = {r.cve_id: r for r in records}
    assert len(by_cve) == 5
    forti = by_cve["CVE-2024-21762"]
    assert forti.id == make_id("vulnerability", "CVE-2024-21762")
    assert forti.published == datetime(2024, 2, 9, 9, 15, 8, 87000, tzinfo=UTC)
    assert forti.cvss_v3_base_score == 9.8 and forti.cvss_v3_severity == "CRITICAL"
    assert forti.cwe_ids == ["CWE-787"]
    assert forti.description and forti.description.startswith("A out-of-bounds write")
    # KEV owns these; NVD rows leave them for gold to merge.
    assert forti.kev_date_added is None
    prov = forti.provenance
    assert prov.source_url == "https://nvd.nist.gov/vuln/detail/CVE-2024-21762"
    assert (prov.parser_id, prov.confidence) == ("nvd", NVD_CONFIDENCE)
    assert prov.license == "LicenseRef-NVD-Terms-of-Use"
    # Duplicate CWE entries (NVD's and the CNA's) are listed once.
    assert by_cve["CVE-2002-0367"].cwe_ids == ["CWE-269"]


def test_rejected_records_are_skipped() -> None:
    assert parse_body(page_with(lambda cve: cve.update(vulnStatus="Rejected"))) == []


def test_cvss_preference() -> None:
    def metric(version: str, score: float, kind: str) -> dict[str, Any]:
        return {
            "type": kind,
            "cvssData": {"version": version, "baseScore": score, "baseSeverity": "HIGH"},
        }

    assert cvss_v3(
        {"cvssMetricV31": [metric("3.1", 7.0, "Secondary"), metric("3.1", 8.0, "Primary")]}
    ) == (8.0, "HIGH")
    assert cvss_v3({"cvssMetricV30": [metric("3.0", 7.5, "Primary")]}) == (7.5, "HIGH")
    assert cvss_v3({"cvssMetricV2": [metric("2.0", 5.0, "Primary")]}) == (None, None)


def test_unknown_severity_fails() -> None:
    def edit(cve: dict[str, Any]) -> None:
        cve["metrics"]["cvssMetricV31"][0]["cvssData"]["baseSeverity"] = "SEVERE"

    with pytest.raises(ValueError, match="SEVERE"):
        parse_body(page_with(edit))


def test_inconsistent_page_fails() -> None:
    page = json.loads((FIXTURES / "page-0.json").read_bytes())
    page["totalResults"] = 1
    with pytest.raises(ValueError, match="more than the 1 total"):
        parse_body(json.dumps(page).encode())


def test_attribution_and_mode() -> None:
    assert NvdParser.meta.mode == "incremental"
    assert NvdCrawler.meta.attribution and "not endorsed" in NvdCrawler.meta.attribution


def test_registered_through_entry_points() -> None:
    assert isinstance(discover_crawlers()["nvd"], NvdCrawler)
    assert isinstance(discover_parsers()["nvd"], NvdParser)
