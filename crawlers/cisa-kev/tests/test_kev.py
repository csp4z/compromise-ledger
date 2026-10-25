import json
from pathlib import Path

import pytest
from ledger_crawl import ParseContext
from ledger_crawl.registry import discover_crawlers, discover_parsers
from ledger_crawl.testing import FIXED_NOW, Fixture, offline_context
from ledger_crawler_cisa_kev import FEED_URL, KevCrawler, KevParser
from ledger_crawler_cisa_kev.parser import KEV_CONFIDENCE, clean_name
from ledger_schemas import ProductMention, Vulnerability, make_id
from pydantic import ValidationError

FIXTURE = Path(__file__).parents[1] / "fixtures" / "known_exploited_vulnerabilities.json"


def fetch_fixture(body: bytes | None = None) -> tuple[bytes, ParseContext]:
    crawler = KevCrawler()
    routes = {FEED_URL: Fixture(body if body is not None else FIXTURE)}
    with offline_context(crawler.meta, routes) as ctx:
        (doc,) = list(crawler.fetch(ctx))
    return doc.body, ParseContext(KevParser.meta, doc.raw, crawler.meta.license)


def parse(body: bytes | None = None) -> list[Vulnerability | ProductMention]:
    return list(KevParser().parse(*fetch_fixture(body)))


def test_crawler_fetches_the_feed() -> None:
    body, ctx = fetch_fixture()
    assert body == FIXTURE.read_bytes()
    assert ctx.raw.source_id == "cisa-kev"
    assert ctx.raw.url == FEED_URL
    assert ctx.raw.fetched_at == FIXED_NOW


def test_one_vulnerability_and_one_mention_per_entry() -> None:
    records = parse()
    vulns = [r for r in records if isinstance(r, Vulnerability)]
    mentions = [r for r in records if isinstance(r, ProductMention)]
    assert len(vulns) == len(mentions) == 6
    assert {m.vulnerability_id for m in mentions} == {v.id for v in vulns}


def test_maps_kev_fields() -> None:
    vuln = next(r for r in parse() if isinstance(r, Vulnerability) and r.cve_id == "CVE-2024-3400")
    assert vuln.id == make_id("vulnerability", "CVE-2024-3400")
    assert vuln.kev_date_added is not None and vuln.kev_date_added.isoformat() == "2024-04-12"
    assert vuln.kev_due_date is not None and vuln.kev_due_date.isoformat() == "2024-04-19"
    assert vuln.kev_ransomware_use == "known"
    assert vuln.cwe_ids == ["CWE-20", "CWE-77"]
    assert vuln.description is not None and "GlobalProtect" in vuln.description
    # NVD owns these fields; KEV leaves them for gold to merge.
    assert vuln.published is None and vuln.cvss_v3_base_score is None


def test_empty_cwes_and_unknown_ransomware_use() -> None:
    vuln = next(r for r in parse() if isinstance(r, Vulnerability) and r.cve_id == "CVE-2015-3246")
    assert vuln.cwe_ids == []
    assert vuln.kev_ransomware_use == "unknown"


def test_names_are_whitespace_normalized_only() -> None:
    names = {(m.vendor_name, m.product_name) for m in parse() if isinstance(m, ProductMention)}
    assert ("SimpleHelp", "SimpleHelp") in names  # upstream: "SimpleHelp "
    assert ("Adobe", "Commerce and Magento") in names  # upstream: narrow no-break space
    assert ("Dassault Systèmes", "DELMIA Apriso") in names  # accents kept
    assert clean_name("  Palo  Alto\u00a0Networks ") == "Palo Alto Networks"


def test_provenance() -> None:
    body, ctx = fetch_fixture()
    for record in KevParser().parse(body, ctx):
        prov = record.provenance
        assert prov.raw_document_id == ctx.raw.id
        assert prov.source_url == FEED_URL
        assert prov.parser_id == "cisa-kev"
        assert prov.confidence == KEV_CONFIDENCE
        assert prov.license == "CC0-1.0"


def test_reparse_is_idempotent() -> None:
    assert [r.id for r in parse()] == [r.id for r in parse()]


def test_count_mismatch_fails() -> None:
    feed = json.loads(FIXTURE.read_bytes())
    feed["count"] += 1
    with pytest.raises(ValueError, match="declares 7 entries"):
        parse(json.dumps(feed).encode())


def test_unexpected_ransomware_value_fails() -> None:
    feed = json.loads(FIXTURE.read_bytes())
    feed["vulnerabilities"][0]["knownRansomwareCampaignUse"] = "Maybe"
    with pytest.raises(ValidationError):
        parse(json.dumps(feed).encode())


def test_registered_through_entry_points() -> None:
    assert isinstance(discover_crawlers()["cisa-kev"], KevCrawler)
    assert isinstance(discover_parsers()["cisa-kev"], KevParser)
