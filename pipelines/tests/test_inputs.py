from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from ledger_crawl import CrawlContext, CrawlerMeta, FetchedDocument, KevCve, RateLimit
from ledger_crawl.registry import discover_crawlers
from ledger_pipelines.config import Settings
from ledger_pipelines.inputs import SourceOrderError, crawl_inputs, crawl_order
from ledger_pipelines.lakehouse import Lakehouse
from ledger_schemas import Provenance, Vulnerability


class Source:
    def __init__(
        self, source_id: str, *, after: tuple[str, ...] = (), inputs: tuple[str, ...] = ()
    ):
        self.meta = CrawlerMeta(
            id=source_id,
            version="0.1.0",
            description="Fake source",
            schedule="0 6 * * *",
            rate_limit=RateLimit(requests=1, per_seconds=1),
            license="CC0-1.0",
            allowed_hosts=("data.example.org",),
            content_types=("application/json",),
            after=after,
            inputs=inputs,  # type: ignore[arg-type]
        )

    def fetch(self, ctx: CrawlContext) -> Iterator[FetchedDocument]:
        return iter(())


def sources(*items: Source) -> dict[str, Source]:
    return {s.meta.id: s for s in items}


def test_sources_run_after_the_ones_they_name_and_otherwise_by_name() -> None:
    crawlers = sources(
        Source("alpha", after=("zulu",)),
        Source("bravo"),
        Source("mike", after=("alpha",)),
        Source("zulu"),
    )
    assert crawl_order(crawlers) == ["bravo", "zulu", "alpha", "mike"]


def test_unknown_and_circular_orders_are_refused() -> None:
    with pytest.raises(SourceOrderError, match="unknown"):
        crawl_order(sources(Source("alpha", after=("missing",))))
    with pytest.raises(SourceOrderError, match="cycle"):
        crawl_order(sources(Source("alpha", after=("bravo",)), Source("bravo", after=("alpha",))))


def test_registered_sources_have_a_valid_order() -> None:
    crawlers = discover_crawlers()
    order = crawl_order(crawlers)
    assert sorted(order) == sorted(crawlers)
    for source_id, crawler in crawlers.items():
        for earlier in crawler.meta.after:
            assert order.index(earlier) < order.index(source_id)


def vulnerability(cve_id: str, parser_id: str, added: date | None) -> Vulnerability:
    return Vulnerability(
        cve_id=cve_id,
        kev_date_added=added,
        provenance=Provenance(
            source_url="https://data.example.org/feed.json",
            raw_document_id="a" * 64,
            crawled_at=datetime(2026, 11, 1, tzinfo=UTC),
            parser_id=parser_id,
            parser_version="0.1.0",
            confidence=95,
            license="CC0-1.0",
        ),
    )


def test_kev_cves_come_from_silver_once_each(settings: Settings) -> None:
    lake = Lakehouse(settings)
    lake.append(
        "silver.vulnerabilities",
        [
            vulnerability("CVE-2024-3400", "cisa-kev", date(2024, 4, 12)),
            vulnerability("CVE-2024-21762", "cisa-kev", date(2024, 2, 9)),
            # Another source's row for a listed CVE, and a CVE that isn't in KEV.
            vulnerability("CVE-2024-21762", "nvd", None),
            vulnerability("CVE-2024-0001", "nvd", None),
        ],
    )
    inputs = crawl_inputs(Source("example", inputs=("kev_cves",)), settings, lake)
    assert inputs.kev_cves == (
        KevCve("CVE-2024-21762", date(2024, 2, 9)),
        KevCve("CVE-2024-3400", date(2024, 4, 12)),
    )
    assert inputs.cpe_vendors == ()  # not asked for, so not loaded


def test_inputs_are_empty_before_the_first_crawl(settings: Settings) -> None:
    lake = Lakehouse(settings)
    assert crawl_inputs(Source("example", inputs=("kev_cves",)), settings, lake).kev_cves == ()
    assert (
        "paloaltonetworks"
        in crawl_inputs(Source("example", inputs=("cpe_vendors",)), settings, lake).cpe_vendors
    )
