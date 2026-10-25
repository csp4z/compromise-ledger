from datetime import UTC, datetime, timedelta

from ledger_crawl import CrawlerMeta, RateLimit
from ledger_pipelines.checks import check
from ledger_schemas import CrawlRun
from ledger_schemas.ops import RunKind, RunStatus

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


class _Crawler:
    def __init__(self, max_age_hours: int = 36) -> None:
        self.meta = CrawlerMeta(
            id="example",
            version="0.1.0",
            description="x",
            schedule="0 6 * * *",
            rate_limit=RateLimit(requests=1, per_seconds=1),
            license="CC0-1.0",
            allowed_hosts=("data.example.org",),
            content_types=("application/json",),
            max_age_hours=max_age_hours,
        )

    def fetch(self, ctx):
        return []


def run(
    kind: RunKind,
    hours_ago: float,
    *,
    status: RunStatus = "succeeded",
    documents: int = 1,
    records: int = 0,
    source_id: str = "example",
    error: str | None = None,
) -> CrawlRun:
    started = NOW - timedelta(hours=hours_ago)
    return CrawlRun(
        run_id=f"{kind}:{source_id}:{hours_ago}",
        kind=kind,
        source_id=source_id,
        plugin_version="0.1.0",
        started_at=started,
        finished_at=started,
        status=status,
        documents=documents,
        records=records,
        error=error if status == "succeeded" else (error or "boom"),
    )


def checks(*runs: CrawlRun, max_age_hours: int = 36) -> list[str]:
    problems = check(list(runs), {"example": _Crawler(max_age_hours)}, now=NOW)
    return [p.check for p in problems]


HEALTHY = [run("crawl", 1), run("parse", 1, records=1000)]


def test_healthy_source_passes() -> None:
    assert checks(*HEALTHY) == []


def test_never_crawled() -> None:
    assert checks() == ["never-crawled"]


def test_failed_crawl_and_staleness() -> None:
    history = [run("crawl", 48), run("parse", 48, records=10), run("crawl", 1, status="failed")]
    assert checks(*history) == ["crawl-failed", "stale"]


def test_freshness_window_is_per_source() -> None:
    history = [run("crawl", 48), run("parse", 48, records=10)]
    assert checks(*history) == ["stale"]
    assert checks(*history, max_age_hours=72) == []


def test_empty_crawl() -> None:
    history = [run("crawl", 30), run("parse", 30, records=5), run("crawl", 1, documents=0)]
    assert checks(*history) == ["empty-crawl"]


def test_parse_failure_and_empty_parse() -> None:
    assert checks(run("crawl", 1), run("parse", 1, status="failed")) == ["parse-failed"]
    assert checks(run("crawl", 1), run("parse", 1, records=0)) == ["empty-parse"]


def test_yield_drop_over_half() -> None:
    assert checks(
        run("crawl", 1), run("parse", 25, records=1000), run("parse", 1, records=499)
    ) == ["yield-drop"]
    assert (
        checks(run("crawl", 1), run("parse", 25, records=1000), run("parse", 1, records=500)) == []
    )


def test_failed_pipeline_steps_are_reported() -> None:
    history = [*HEALTHY, run("export", 1, status="failed", source_id="export")]
    assert checks(*history) == ["export-failed"]
    history.append(run("export", 0.5, source_id="export"))
    assert checks(*history) == []
