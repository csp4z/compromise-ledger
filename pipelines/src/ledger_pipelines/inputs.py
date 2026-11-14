"""Fills ``CrawlerMeta.inputs`` from the seeds and silver, and orders sources by
``CrawlerMeta.after`` (see ``ledger_crawl.inputs``)."""

from collections.abc import Callable, Mapping
from datetime import date
from graphlib import CycleError, TopologicalSorter

from ledger_crawl import Crawler, CrawlInputs, KevCve
from ledger_crawl.inputs import InputName

from ledger_pipelines.config import Settings
from ledger_pipelines.lakehouse import Lakehouse
from ledger_pipelines.resolve import load_seeds


class SourceOrderError(ValueError):
    """``CrawlerMeta.after`` names an unknown source or forms a cycle."""


def _cpe_vendors(settings: Settings, lake: Lakehouse) -> tuple[str, ...]:
    return load_seeds(settings.seeds_dir).cpe_vendors


def _kev_cves(settings: Settings, lake: Lakehouse) -> tuple[KevCve, ...]:
    """KEV rows in silver, uncorrected: a crawler may fetch a record that gold later leaves
    out, and what it fetched stays out of every published table."""
    rows = lake.read("silver.vulnerabilities").select(["cve_id", "kev_date_added"]).to_pylist()
    added: dict[str, date] = {}
    for row in rows:
        if row["kev_date_added"] is not None:
            added[row["cve_id"]] = min(row["kev_date_added"], added.get(row["cve_id"], date.max))
    return tuple(KevCve(cve_id, added[cve_id]) for cve_id in sorted(added))


_PROVIDERS: dict[InputName, Callable[[Settings, Lakehouse], tuple[object, ...]]] = {
    "cpe_vendors": _cpe_vendors,
    "kev_cves": _kev_cves,
}


def crawl_inputs(crawler: Crawler, settings: Settings, lake: Lakehouse) -> CrawlInputs:
    """Only the inputs the crawler declares; the rest stay empty and unread."""
    return CrawlInputs(**{name: _PROVIDERS[name](settings, lake) for name in crawler.meta.inputs})  # type: ignore[arg-type]


def crawl_order(crawlers: Mapping[str, Crawler]) -> list[str]:
    """Source IDs with every source after the ones it names in ``after``; ties run by name."""
    sorter: TopologicalSorter[str] = TopologicalSorter()
    for source_id in sorted(crawlers):
        missing = [s for s in crawlers[source_id].meta.after if s not in crawlers]
        if missing:
            raise SourceOrderError(f"{source_id} runs after unknown source(s): {missing}")
        sorter.add(source_id, *crawlers[source_id].meta.after)
    try:
        sorter.prepare()
    except CycleError as exc:
        raise SourceOrderError(f"sources depend on each other in a cycle: {exc.args[1]}") from exc
    order: list[str] = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready())
        order.extend(ready)
        sorter.done(*ready)
    return order
