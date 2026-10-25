"""Health checks over ``ops.crawl_runs`` (``ledger check``)."""

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from ledger_crawl import Crawler
from ledger_schemas import CrawlRun

YIELD_DROP_LIMIT = 0.5  # fail when a parse yields less than half the previous good parse
PIPELINE_STEPS = (("resolve", "vendor-resolution"), ("build", "gold"), ("export", "export"))


@dataclass(frozen=True, slots=True)
class Problem:
    source_id: str
    check: str
    message: str

    def __str__(self) -> str:
        return f"{self.source_id}: {self.check}: {self.message}"


def _history(runs: Iterable[CrawlRun], kind: str, source_id: str) -> list[CrawlRun]:
    """Newest first."""
    matching = [r for r in runs if r.kind == kind and r.source_id == source_id]
    return sorted(matching, key=lambda r: r.started_at, reverse=True)


def _check_source(
    source_id: str, max_age: timedelta, runs: Sequence[CrawlRun], now: datetime
) -> Iterator[Problem]:
    crawls = _history(runs, "crawl", source_id)
    if not crawls:
        yield Problem(source_id, "never-crawled", "no crawl has run")
        return
    latest = crawls[0]
    if latest.status == "failed":
        yield Problem(source_id, "crawl-failed", latest.error or "unknown error")
    elif latest.documents == 0:
        yield Problem(source_id, "empty-crawl", "the latest crawl returned no documents")
    good = [r for r in crawls if r.status == "succeeded" and r.documents > 0]
    if not good:
        yield Problem(source_id, "stale", "no successful crawl yet")
    elif now - good[0].started_at > max_age:
        hours = (now - good[0].started_at).total_seconds() / 3600
        yield Problem(source_id, "stale", f"last good crawl {hours:.0f}h ago (limit {max_age})")

    parses = _history(runs, "parse", source_id)
    if not parses:
        yield Problem(source_id, "never-parsed", "no parse has run")
        return
    if parses[0].status == "failed":
        yield Problem(source_id, "parse-failed", parses[0].error or "unknown error")
        return
    if parses[0].records == 0:
        yield Problem(source_id, "empty-parse", "the latest parse produced no records")
        return
    previous = next((r for r in parses[1:] if r.status == "succeeded" and r.records), None)
    if previous and parses[0].records < previous.records * YIELD_DROP_LIMIT:
        yield Problem(
            source_id,
            "yield-drop",
            f"{parses[0].records} records, down from {previous.records}",
        )


def check(
    runs: Sequence[CrawlRun], crawlers: Mapping[str, Crawler], *, now: datetime
) -> list[Problem]:
    problems: list[Problem] = []
    for source_id, crawler in sorted(crawlers.items()):
        max_age = timedelta(hours=crawler.meta.max_age_hours)
        problems.extend(_check_source(source_id, max_age, runs, now))
    for kind, source_id in PIPELINE_STEPS:
        history = _history(runs, kind, source_id)
        if history and history[0].status == "failed":
            problems.append(Problem(source_id, f"{kind}-failed", history[0].error or "unknown"))
    return problems
