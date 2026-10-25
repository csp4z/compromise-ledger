"""Crawler plugin SDK: the fetch -> RawDocument contract, crawl context, and plugin registry."""

from importlib.metadata import version

from ledger_crawl.context import CrawlContext, FetchedDocument
from ledger_crawl.meta import CrawlerMeta, ParserMeta, RateLimit
from ledger_crawl.plugin import Crawler, ParseContext, Parser

__version__ = version("ledger-crawl")

__all__ = [
    "CrawlContext",
    "Crawler",
    "CrawlerMeta",
    "FetchedDocument",
    "ParseContext",
    "Parser",
    "ParserMeta",
    "RateLimit",
]
