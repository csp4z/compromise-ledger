from collections.abc import Iterable
from datetime import UTC, datetime

import pytest
from ledger_crawl import (
    CrawlContext,
    CrawlerMeta,
    FetchedDocument,
    ParseContext,
    ParserMeta,
    registry,
)
from ledger_crawl.registry import PluginError, discover_crawlers, discover_parsers
from ledger_schemas import RawDocument, Vulnerability
from pydantic import BaseModel

PARSER_META = ParserMeta(id="example", version="0.2.0", source_id="example", confidence=80)
RAW = RawDocument(
    id="c" * 64,
    source_id="example",
    crawler_version="0.1.0",
    url="https://data.example.org/feed.json",
    fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
    http_status=200,
    content_type="application/json",
    size_bytes=2,
)


def test_parse_context_fills_provenance() -> None:
    ctx = ParseContext(parser=PARSER_META, raw=RAW, license="CC0-1.0")
    prov = ctx.provenance()
    assert prov.raw_document_id == RAW.id
    assert prov.source_url == RAW.url
    assert prov.crawled_at == RAW.fetched_at
    assert (prov.parser_id, prov.parser_version, prov.confidence) == ("example", "0.2.0", 80)
    assert prov.license == "CC0-1.0"
    own = ctx.provenance(source_url="https://data.example.org/item/1", confidence=95)
    assert (own.source_url, own.confidence) == ("https://data.example.org/item/1", 95)


class FakeEntryPoint:
    def __init__(self, name: str, obj: object) -> None:
        self.name = name
        self.value = f"tests:{name}"
        self._obj = obj

    def load(self) -> object:
        return self._obj


def make_crawler(meta: CrawlerMeta) -> type:
    class _Crawler:
        def __init__(self) -> None:
            self.meta = meta

        def fetch(self, ctx: CrawlContext) -> Iterable[FetchedDocument]:
            return []

    return _Crawler


class _Parser:
    meta = PARSER_META

    def parse(self, body: bytes, ctx: ParseContext) -> Iterable[BaseModel]:
        yield Vulnerability(cve_id="CVE-2024-3400", provenance=ctx.provenance())


def patch_entry_points(monkeypatch: pytest.MonkeyPatch, group_map: dict[str, list[object]]) -> None:
    monkeypatch.setattr(registry, "entry_points", lambda group: group_map.get(group, []))


def test_discovers_clearnet_and_hides_tor(
    monkeypatch: pytest.MonkeyPatch, meta: CrawlerMeta
) -> None:
    tor_meta = meta.model_copy(update={"id": "leaks", "network": "tor"})
    patch_entry_points(
        monkeypatch,
        {
            registry.CRAWLERS_GROUP: [
                FakeEntryPoint("example", make_crawler(meta)),
                FakeEntryPoint("leaks", make_crawler(tor_meta)),
            ]
        },
    )
    assert list(discover_crawlers()) == ["example"]
    assert list(discover_crawlers("tor")) == ["leaks"]


def test_entry_point_name_must_match_meta_id(
    monkeypatch: pytest.MonkeyPatch, meta: CrawlerMeta
) -> None:
    patch_entry_points(
        monkeypatch, {registry.CRAWLERS_GROUP: [FakeEntryPoint("other", make_crawler(meta))]}
    )
    with pytest.raises(PluginError, match="registers crawler"):
        discover_crawlers()


def test_rejects_objects_that_are_not_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_entry_points(monkeypatch, {registry.PARSERS_GROUP: [FakeEntryPoint("x", object())]})
    with pytest.raises(PluginError, match="does not implement Parser"):
        discover_parsers()


def test_discovers_parsers(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_entry_points(monkeypatch, {registry.PARSERS_GROUP: [FakeEntryPoint("example", _Parser)]})
    parsers = discover_parsers()
    records = list(parsers["example"].parse(b"{}", ParseContext(PARSER_META, RAW, "CC0-1.0")))
    assert records[0].model_dump()["provenance"]["parser_id"] == "example"
