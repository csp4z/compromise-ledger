import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from ledger_crawl import CrawlInputs, FetchedDocument, KevCve, ParseContext
from ledger_crawl.registry import discover_crawlers, discover_parsers
from ledger_crawl.testing import Fixture, offline_context
from ledger_crawler_epss import API_URL, EpssCrawler, EpssParser, score_params
from ledger_crawler_epss.crawler import BATCH, batches
from ledger_crawler_epss.parser import EPSS_CONFIDENCE
from ledger_schemas import EpssScore, make_id

FIXTURES = Path(__file__).parents[1] / "fixtures"
LISTINGS = {
    date(2024, 1, 10): ["CVE-2023-46805", "CVE-2024-21887"],
    date(2024, 6, 26): ["CVE-2020-13965", "CVE-2022-24816", "CVE-2022-2586"],
    date(2024, 7, 9): ["CVE-2024-23692", "CVE-2024-38080", "CVE-2024-38112"],
}
KEV = tuple(KevCve(cve_id, added) for added, cves in LISTINGS.items() for cve_id in cves)


def url(cve_ids: list[str], day: date) -> str:
    return str(httpx.URL(API_URL, params=score_params(cve_ids, day)))


JAN, JUN, JUL = (
    url(LISTINGS[date(2024, 1, 10)], date(2024, 1, 9)),
    url(LISTINGS[date(2024, 6, 26)], date(2024, 6, 25)),
    url(LISTINGS[date(2024, 7, 9)], date(2024, 7, 8)),
)
ROUTES = {
    JAN: Fixture(FIXTURES / "2024-01-09.json"),
    JUN: Fixture(FIXTURES / "2024-06-25.json"),
    JUL: Fixture(FIXTURES / "2024-07-08.json"),
}


def crawl(
    routes: dict[str, Fixture] = ROUTES,
    *,
    kev: tuple[KevCve, ...] = KEV,
    seen: frozenset[str] = frozenset(),
) -> list[FetchedDocument]:
    crawler = EpssCrawler()
    with offline_context(
        crawler.meta, routes, inputs=CrawlInputs(kev_cves=kev), seen_urls=seen
    ) as ctx:
        return list(crawler.fetch(ctx))


def parse(doc: FetchedDocument) -> list[EpssScore]:
    ctx = ParseContext(EpssParser.meta, doc.raw, EpssCrawler.meta.license)
    return list(EpssParser().parse(doc.body, ctx))


def test_asks_for_each_listing_dates_cves_on_the_day_before() -> None:
    assert [d.raw.url for d in crawl()] == [JAN, JUN, JUL]


def test_dates_in_bronze_are_skipped_except_the_newest() -> None:
    assert [d.raw.url for d in crawl(seen=frozenset({JAN, JUN, JUL}))] == [JUL]
    assert [d.raw.url for d in crawl(seen=frozenset({JAN}))] == [JUN, JUL]


def test_a_large_listing_day_is_split_into_batches() -> None:
    launch = tuple(KevCve(f"CVE-2021-{n:05d}", date(2021, 11, 3)) for n in range(BATCH * 2 + 7))
    sizes = [(day, len(cve_ids)) for day, cve_ids in batches(launch)]
    assert sizes == [(date(2021, 11, 2), BATCH), (date(2021, 11, 2), BATCH), (date(2021, 11, 2), 7)]


def test_a_date_without_scores_does_not_stop_the_rest() -> None:
    routes = ROUTES | {JAN: Fixture(b"{}", status=422)}
    assert [d.raw.url for d in crawl(routes)] == [JUN, JUL]
    with pytest.raises(Exception, match="503"):
        crawl(ROUTES | {JAN: Fixture(b"", status=503)})


def test_needs_kev_first() -> None:
    with pytest.raises(ValueError, match="cisa-kev"):
        crawl(kev=())
    assert EpssCrawler.meta.after == ("cisa-kev",)


def test_parses_scores() -> None:
    _, june, july = crawl()
    scores = {s.cve_id: s for s in parse(june)}
    assert set(scores) == set(LISTINGS[date(2024, 6, 26)])
    geoserver = scores["CVE-2022-24816"]
    assert geoserver.id == make_id("x-ledger-epss-score", "CVE-2022-24816", "2024-06-25")
    assert geoserver.vulnerability_id == make_id("vulnerability", "CVE-2022-24816")
    assert (geoserver.epss, geoserver.percentile) == (0.8217, 0.98419)
    assert geoserver.score_date == date(2024, 6, 25)
    prov = geoserver.provenance
    assert prov.source_url == JUN
    assert (prov.parser_id, prov.confidence) == ("epss", EPSS_CONFIDENCE)
    # Two of July's three CVEs were published on the day CISA listed them: no score before.
    assert [s.cve_id for s in parse(july)] == ["CVE-2024-23692"]


def test_cves_not_public_yet_have_no_score() -> None:
    january, _, _ = crawl()
    assert parse(january) == []


def test_a_truncated_or_failed_page_fails() -> None:
    page = json.loads((FIXTURES / "2024-06-25.json").read_bytes())
    (doc,) = crawl(
        {JUN: Fixture(json.dumps(page | {"total": 4}).encode())}, kev=KEV[2:5], seen=frozenset()
    )
    with pytest.raises(ValueError, match="cut short"):
        parse(doc)
    (doc,) = crawl({JUN: Fixture(json.dumps(page | {"status": "ERROR"}).encode())}, kev=KEV[2:5])
    with pytest.raises(ValueError, match="ERROR"):
        parse(doc)


def test_attribution_and_mode() -> None:
    assert EpssParser.meta.mode == "incremental"
    attribution = EpssCrawler.meta.attribution
    assert attribution and "FIRST" in attribution and "Empirical Security" in attribution


def test_registered_through_entry_points() -> None:
    assert isinstance(discover_crawlers()["epss"], EpssCrawler)
    assert isinstance(discover_parsers()["epss"], EpssParser)
