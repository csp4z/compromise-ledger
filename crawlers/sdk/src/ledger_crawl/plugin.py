"""The plugin contract: crawlers fetch, parsers turn raw documents into silver records."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ledger_schemas import Provenance, RawDocument
from pydantic import BaseModel

from ledger_crawl.context import CrawlContext, FetchedDocument
from ledger_crawl.meta import CrawlerMeta, ParserMeta


@runtime_checkable
class Crawler(Protocol):
    meta: CrawlerMeta

    def fetch(self, ctx: CrawlContext) -> Iterable[FetchedDocument]:
        """Fetch documents through ``ctx`` only. Never parse, store, or follow file links."""
        ...


@dataclass(frozen=True, slots=True)
class ParseContext:
    """What a parser knows about the document it is parsing."""

    parser: ParserMeta
    raw: RawDocument
    license: str

    def provenance(
        self, *, source_url: str | None = None, confidence: int | None = None
    ) -> Provenance:
        """Provenance for a record parsed from this document.

        ``source_url`` defaults to the fetched URL; pass the record's own page when the source
        has one. ``confidence`` defaults to the parser's.
        """
        return Provenance(
            source_url=source_url or self.raw.url,
            raw_document_id=self.raw.id,
            crawled_at=self.raw.fetched_at,
            parser_id=self.parser.id,
            parser_version=self.parser.version,
            confidence=self.parser.confidence if confidence is None else confidence,
            license=self.license,
        )


@runtime_checkable
class Parser(Protocol):
    meta: ParserMeta

    def parse(self, body: bytes, ctx: ParseContext) -> Iterable[BaseModel]:
        """Yield silver records (ledger_schemas models), each with ``ctx.provenance()``."""
        ...
