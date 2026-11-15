"""Crawler plugin SDK: the fetch -> RawDocument contract, crawl context, and plugin registry."""

from importlib.metadata import version

from ledger_crawl.context import TRANSIENT_ERRORS, CrawlContext, FetchedDocument
from ledger_crawl.inputs import CrawlInputs, KevCve
from ledger_crawl.meta import CrawlerMeta, ParserMeta, RateLimit
from ledger_crawl.plugin import Crawler, ParseContext, Parser

__version__ = version("ledger-crawl")

__all__ = [
    "TRANSIENT_ERRORS",
    "CrawlContext",
    "CrawlInputs",
    "Crawler",
    "CrawlerMeta",
    "FetchedDocument",
    "KevCve",
    "ParseContext",
    "Parser",
    "ParserMeta",
    "RateLimit",
]
