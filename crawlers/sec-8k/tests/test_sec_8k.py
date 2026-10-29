import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from ledger_crawl import FetchedDocument, ParseContext
from ledger_crawl.registry import discover_crawlers, discover_parsers
from ledger_crawl.testing import FIXED_NOW, Fixture, offline_context
from ledger_crawler_sec_8k import SEARCH_URL, Sec8kCrawler, Sec8kParser, search_params
from ledger_crawler_sec_8k.crawler import FORMS, OVERLAP, PHRASES, RULE_START
from ledger_crawler_sec_8k.parser import ITEM_105_CONFIDENCE, ITEM_801_CONFIDENCE
from ledger_schemas import Incident, Organization, make_id

FIXTURES = Path(__file__).parents[1] / "fixtures"
IDENTIFIED = FIXTURES / "identified-incident-8k.json"
CYBER = FIXTURES / "cybersecurity-incident-8k.json"
AMENDMENTS = FIXTURES / "item-105-8ka.json"
EMPTY = FIXTURES / "empty.json"
TODAY = FIXED_NOW.date()


def url(phrase: str, form: str, start: date, offset: int = 0) -> str:
    params = search_params(phrase, form, start, TODAY, offset)  # type: ignore[arg-type]
    return str(httpx.URL(SEARCH_URL, params=params))


def empty_routes(start: date) -> dict[str, Fixture]:
    return {url(p, f, start): Fixture(EMPTY) for p in PHRASES for f in FORMS}


def crawl(routes: dict[str, Fixture], **kwargs: Any) -> list[FetchedDocument]:
    crawler = Sec8kCrawler()
    with offline_context(crawler.meta, routes, **kwargs) as ctx:
        return list(crawler.fetch(ctx))


def parse(body: bytes) -> list[Organization | Incident]:
    (doc, *_) = crawl(
        {**empty_routes(RULE_START), url(*PHRASES[:1], "8-K", RULE_START): Fixture(body)}
    )
    ctx = ParseContext(Sec8kParser.meta, doc.raw, Sec8kCrawler.meta.license)
    return list(Sec8kParser().parse(doc.body, ctx))


def page(hits: list[Any], total: int) -> bytes:
    data = json.loads(CYBER.read_bytes())
    data["hits"]["hits"] = hits
    data["hits"]["total"]["value"] = total
    return json.dumps(data).encode()


def test_first_run_searches_every_phrase_and_form_since_the_rule() -> None:
    docs = crawl(empty_routes(RULE_START))
    assert len(docs) == len(PHRASES) * len(FORMS)
    assert all(d.raw.source_id == "sec-8k" for d in docs)


def test_later_runs_search_since_the_last_run() -> None:
    last = FIXED_NOW - timedelta(days=1)
    start = (last - OVERLAP).date()
    assert len(crawl(empty_routes(start), last_success=last)) == len(PHRASES) * len(FORMS)


def test_pages_through_results() -> None:
    hits = json.loads(CYBER.read_bytes())["hits"]["hits"]
    phrase = PHRASES[0]
    routes = {
        **empty_routes(RULE_START),
        url(phrase, "8-K", RULE_START): Fixture(page(hits[:3], 5)),
        url(phrase, "8-K", RULE_START, 3): Fixture(page(hits[3:5], 5)),
    }
    assert len(crawl(routes)) == len(PHRASES) * len(FORMS) + 1


def test_refuses_more_results_than_search_can_page() -> None:
    routes = {
        **empty_routes(RULE_START),
        url(PHRASES[0], "8-K", RULE_START): Fixture(page([], 20_000)),
    }
    with pytest.raises(ValueError, match="more than search can page"):
        crawl(routes)


def test_keeps_item_105_and_801_disclosures() -> None:
    records = parse(IDENTIFIED.read_bytes())
    incidents = {r.sec_accession: r for r in records if isinstance(r, Incident)}
    # Of 15 hits: 4 report Item 1.05 and 8 are 8.01 disclosures in the 8-K itself. Stryker's
    # 7.01 updates and a Zoomcar financing exhibit are dropped.
    assert sorted(i.sec_item for i in incidents.values()) == ["1.05"] * 4 + ["8.01"] * 8
    boston = incidents["0000885725-26-000059"]
    assert (boston.status, boston.sec_form, boston.sec_item, boston.disclosed_on) == (
        "confirmed",
        "8-K",
        "1.05",
        date(2026, 9, 8),
    )
    assert boston.provenance.confidence == ITEM_105_CONFIDENCE
    assert boston.provenance.source_url == (
        "https://www.sec.gov/Archives/edgar/data/885725/000088572526000059/"
        "0000885725-26-000059-index.htm"
    )
    # The same company's earlier 8.01 filing about the incident is its own record.
    assert incidents["0000885725-26-000056"].provenance.confidence == ITEM_801_CONFIDENCE
    orgs = {r.sec_cik: r for r in records if isinstance(r, Organization)}
    assert boston.organization_id == make_id("identity", "sec-cik", "0000885725")
    assert (orgs["0000885725"].name, orgs["0000885725"].tickers) == (
        "BOSTON SCIENTIFIC CORP",
        ["BSX"],
    )
    assert orgs["0001854275"].tickers == ["ZCAR", "ZCARW"]  # Zoomcar: two tickers


def test_drops_exhibits_and_filings_about_other_business() -> None:
    incidents = {r.sec_accession: r for r in parse(CYBER.read_bytes()) if isinstance(r, Incident)}
    assert "0001628280-26-060735" not in incidents  # phrase only in a press release (EX-99.1)
    assert "0001020859-26-000022" not in incidents  # earnings (Item 2.02)
    assert "0001907982-26-000141" not in incidents  # merger exhibit (EX-10.1)
    assert len(incidents) == 7


def test_display_name_without_ticker() -> None:
    orgs = {r.sec_cik: r for r in parse(CYBER.read_bytes()) if isinstance(r, Organization)}
    assert orgs["0001124804"].name == "Veradigm Inc."
    assert orgs["0001124804"].tickers == []


def test_amendments_keep_their_form() -> None:
    incidents = [r for r in parse(AMENDMENTS.read_bytes()) if isinstance(r, Incident)]
    assert len(incidents) == 26
    assert {(i.sec_form, i.sec_item) for i in incidents} == {("8-K/A", "1.05")}


def test_empty_page_yields_nothing() -> None:
    assert parse(EMPTY.read_bytes()) == []


def test_registered_under_its_id() -> None:
    assert "sec-8k" in discover_crawlers()
    assert "sec-8k" in discover_parsers()
