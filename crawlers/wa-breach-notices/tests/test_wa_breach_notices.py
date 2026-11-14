import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from ledger_crawl import FetchedDocument, ParseContext
from ledger_crawl.registry import discover_crawlers, discover_parsers
from ledger_crawl.testing import Fixture, offline_context
from ledger_crawler_wa_breach_notices import WaBreachNoticeCrawler, WaBreachNoticeParser, url
from ledger_crawler_wa_breach_notices.crawler import LIMIT
from ledger_crawler_wa_breach_notices.parser import WA_CONFIDENCE, publishable_name
from ledger_schemas import BreachNotice, make_id

FIXTURES = Path(__file__).parents[1] / "fixtures"


def crawl(body: bytes | Path = FIXTURES / "notices.json") -> FetchedDocument:
    crawler = WaBreachNoticeCrawler()
    with offline_context(crawler.meta, {url(): Fixture(body)}) as ctx:
        (doc,) = crawler.fetch(ctx)
    return doc


def parse(doc: FetchedDocument) -> list[BreachNotice]:
    ctx = ParseContext(WaBreachNoticeParser.meta, doc.raw, WaBreachNoticeCrawler.meta.license)
    return list(WaBreachNoticeParser().parse(doc.body, ctx))


def notices() -> dict[str, BreachNotice]:
    return {n.notice_id: n for n in parse(crawl())}


def with_row(**changes: Any) -> bytes:
    row = json.loads((FIXTURES / "notices.json").read_bytes())[0] | changes
    return json.dumps([row]).encode()


def test_one_request_for_the_whole_dataset() -> None:
    doc = crawl()
    assert doc.raw.url == url()
    assert "%24limit=50000" in url() and "%24order=id" in url()
    assert doc.raw.source_id == "wa-breach-notices"


def test_parses_a_ransomware_notice() -> None:
    notice = notices()["11394"]
    assert notice.id == make_id("incident", "breach-notice", "us-wa", "11394")
    assert notice.organization_name == "Accutech Systems Corporation"
    assert notice.status == "confirmed"
    assert (notice.cause, notice.attack_type) == ("cyberattack", "ransomware")
    assert notice.breach_started_on == notice.aware_on == date(2021, 8, 16)
    assert notice.submitted_on == date(2022, 1, 28)
    assert (notice.industry, notice.organization_state) == ("Business", "IN")
    assert notice.residents_affected == 1376
    prov = notice.provenance
    assert (prov.parser_id, prov.confidence, prov.source_url) == (
        "wa-breach-notices",
        WA_CONFIDENCE,
        url(),
    )
    assert prov.license == "LicenseRef-WA-AGO-No-Stated-License"


def test_every_cause_and_attack_type_maps() -> None:
    parsed = notices().values()
    assert len(parsed) == 16
    assert {n.cause for n in parsed} == {"cyberattack", "unauthorized-access", "theft-or-mistake"}
    assert {n.attack_type for n in parsed} == {
        "ransomware",
        "malware",
        "phishing",
        "skimmer",
        "other",
        "unknown",
        None,
    }


def test_missing_and_untidy_values() -> None:
    parsed = notices()
    assert parsed["9589"].aware_on is None  # no awareness date on the notice
    assert parsed["9563"].breach_started_on is None
    assert parsed["9566"].residents_affected is None
    assert parsed["10691"].organization_state == "WA"  # "WA " upstream
    assert parsed["15308"].organization_state is None  # "Iowa" upstream: not guessed
    assert parsed["11374"].organization_name == "Nuna Baby Essentials, Inc."  # trailing space
    # Dates are kept as reported, even a breach dated after the organization knew of it.
    keller = parsed["11424"]
    assert keller.breach_started_on and keller.aware_on
    assert keller.breach_started_on > keller.aware_on


def test_practice_names_are_withheld() -> None:
    assert notices()["13508"].organization_name is None  # "..., P.C."
    for name in ("Jane Roe DDS PLLC", "Law Office of J. Roe", "Roe & Roe, P.S.", "Dr. J. Roe"):
        assert publishable_name(name) is None
    for name in ("T-Mobile USA", "PCC Structurals", "Pacific Lutheran University", "MDLIVE Inc"):
        assert publishable_name(name) == name


def test_unknown_vocabulary_fails() -> None:
    with pytest.raises(ValueError, match="cause 'Sabotage'"):
        parse(crawl(with_row(databreachcause="Sabotage")))
    with pytest.raises(ValueError, match="attack type 'Wiper'"):
        parse(crawl(with_row(cyberattacktype="Wiper")))


def test_a_full_page_fails() -> None:
    row = json.loads((FIXTURES / "notices.json").read_bytes())[0]
    with pytest.raises(ValueError, match="cut off"):
        parse(crawl(json.dumps([row] * LIMIT).encode()))


def test_empty_dataset_parses_to_nothing() -> None:
    assert parse(crawl(FIXTURES / "empty.json")) == []


def test_snapshot_mode_and_attribution() -> None:
    assert WaBreachNoticeParser.meta.mode == "snapshot"
    attribution = WaBreachNoticeCrawler.meta.attribution
    assert attribution and "Attorney General" in attribution


def test_registered_through_entry_points() -> None:
    assert isinstance(discover_crawlers()["wa-breach-notices"], WaBreachNoticeCrawler)
    assert isinstance(discover_parsers()["wa-breach-notices"], WaBreachNoticeParser)
