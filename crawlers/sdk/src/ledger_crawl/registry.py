"""Plugin discovery through entry points.

A plugin package registers its classes in ``pyproject.toml``::

    [project.entry-points."ledger.crawlers"]
    cisa-kev = "ledger_crawler_cisa_kev:KevCrawler"

    [project.entry-points."ledger.parsers"]
    cisa-kev = "ledger_crawler_cisa_kev:KevParser"
"""

from importlib.metadata import EntryPoint, entry_points

from ledger_crawl.meta import Network
from ledger_crawl.plugin import Crawler, Parser

CRAWLERS_GROUP = "ledger.crawlers"
PARSERS_GROUP = "ledger.parsers"


class PluginError(Exception):
    """A plugin is missing, malformed, or registered under the wrong name."""


def _instantiate(ep: EntryPoint) -> object:
    obj = ep.load()
    return obj() if isinstance(obj, type) else obj


def discover_crawlers(network: Network = "clearnet") -> dict[str, Crawler]:
    """Crawlers for one network. Tor crawlers are only loaded when asked for explicitly,
    which only the isolated Tor runner does."""
    found: dict[str, Crawler] = {}
    for ep in entry_points(group=CRAWLERS_GROUP):
        crawler = _instantiate(ep)
        if not isinstance(crawler, Crawler):
            raise PluginError(f"{ep.value} does not implement Crawler")
        if crawler.meta.id != ep.name:
            raise PluginError(f"entry point {ep.name!r} registers crawler {crawler.meta.id!r}")
        if crawler.meta.network == network:
            found[ep.name] = crawler
    return found


def discover_parsers() -> dict[str, Parser]:
    found: dict[str, Parser] = {}
    for ep in entry_points(group=PARSERS_GROUP):
        parser = _instantiate(ep)
        if not isinstance(parser, Parser):
            raise PluginError(f"{ep.value} does not implement Parser")
        if parser.meta.id != ep.name:
            raise PluginError(f"entry point {ep.name!r} registers parser {parser.meta.id!r}")
        found[ep.name] = parser
    return found
