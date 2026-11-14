import json
import stat
from collections.abc import Iterable, Iterator
from pathlib import Path

import dagster as dg
import pytest
from ledger_crawl import (
    CrawlContext,
    CrawlerMeta,
    FetchedDocument,
    ParseContext,
    ParserMeta,
    RateLimit,
)
from ledger_crawl.registry import discover_crawlers
from ledger_crawl.testing import Fixture, fixture_transport
from ledger_orchestration.definitions import (
    SCHEDULE,
    Ledger,
    alerted_already,
    build_assets,
    build_definitions,
    source_key,
)
from ledger_pipelines.config import Settings
from ledger_pipelines.runner import Runner
from ledger_schemas import ProductMention, Vulnerability
from pydantic import BaseModel

FEED = "https://data.example.org/feed.json"


class Source:
    def __init__(self, source_id: str, after: tuple[str, ...] = ()) -> None:
        self.meta = CrawlerMeta(
            id=source_id,
            version="0.1.0",
            description=f"Fake source {source_id}",
            schedule="0 6 * * *",
            rate_limit=RateLimit(requests=100, per_seconds=1),
            license="CC0-1.0",
            allowed_hosts=("data.example.org",),
            content_types=("application/json",),
            after=after,
        )
        self.url = f"https://data.example.org/{source_id}.json"

    def fetch(self, ctx: CrawlContext) -> Iterator[FetchedDocument]:
        yield ctx.get(self.url)


class Parser:
    def __init__(self, source_id: str) -> None:
        self.meta = ParserMeta(id=source_id, version="0.1.0", source_id=source_id, confidence=90)

    def parse(self, body: bytes, ctx: ParseContext) -> Iterable[BaseModel]:
        for cve, vendor, product in json.loads(body):
            vuln = Vulnerability(cve_id=cve, provenance=ctx.provenance())
            yield vuln
            yield ProductMention(
                vulnerability_id=vuln.id,
                vendor_name=vendor,
                product_name=product,
                provenance=ctx.provenance(),
            )


ROWS = [["CVE-2024-3400", "Palo Alto Networks", "PAN-OS"]]
SOURCES = {"alpha": Source("alpha"), "bravo": Source("bravo", after=("alpha",))}


def ledger(settings: Settings, *, broken: str | None = None) -> Ledger:
    routes = {
        s.url: Fixture(b"", status=503) if sid == broken else Fixture(json.dumps(ROWS).encode())
        for sid, s in SOURCES.items()
    }
    runner = Runner(
        settings,
        crawlers=SOURCES,
        parsers={sid: Parser(sid) for sid in SOURCES},
        transport=fixture_transport(routes),
    )
    return Ledger(runner, settings)


def run(resource: Ledger) -> dg.ExecuteInProcessResult:
    return dg.materialize(
        build_assets(SOURCES), resources={"ledger": resource}, raise_on_error=False
    )


def materialized(result: dg.ExecuteInProcessResult) -> set[str]:
    events = result.get_asset_materialization_events()
    return {e.asset_key.to_user_string() for e in events if e.asset_key}


def checks(result: dg.ExecuteInProcessResult) -> dict[str, bool]:
    evaluations = [
        e.asset_check_evaluation_data
        for e in result.all_events
        if e.event_type == dg.DagsterEventType.ASSET_CHECK_EVALUATION
    ]
    return {e.asset_key.to_user_string(): e.passed for e in evaluations}


@pytest.fixture(autouse=True)
def no_publishing(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CL_PUBLISH_SITE_SCRIPT", "CL_BACKUP_DIR", "CL_NTFY_URL", "CL_HEALTHCHECKS_URL"):
        monkeypatch.delenv(name, raising=False)


def test_definitions_load_with_the_registered_sources() -> None:
    defs = build_definitions()
    dg.Definitions.validate_loadable(defs)
    graph = defs.resolve_asset_graph()
    crawlers = discover_crawlers()
    for source_id, crawler in crawlers.items():
        upstream = graph.get(source_key(source_id)).parent_keys
        assert upstream == {source_key(s) for s in crawler.meta.after}
    # The daily job and the implicit job behind the UI's "Materialize" both run in one process.
    assert defs.resolve_job_def("daily").executor_def.name == "in_process"
    assert defs.resolve_implicit_global_asset_job_def().executor_def.name == "in_process"
    schedule = defs.resolve_schedule_def("daily_schedule")
    assert schedule.cron_schedule == SCHEDULE and schedule.execution_timezone == "UTC"


def test_a_healthy_run_materializes_every_step(settings: Settings) -> None:
    result = run(ledger(settings))
    assert result.success
    assert materialized(result) == {
        "source/alpha",
        "source/bravo",
        "vendor_resolution",
        "exports",
        "site",
        "maintenance",
        "backup_archive",
        "health",
    }
    assert checks(result) == {"source/alpha": True, "source/bravo": True}
    assert (settings.exports_dir / "datasets.json").exists()


def test_a_broken_source_fails_its_check_and_the_run_but_not_the_other_steps(
    settings: Settings,
) -> None:
    result = run(ledger(settings, broken="alpha"))
    assert not result.success
    assert checks(result) == {"source/alpha": False, "source/bravo": True}
    # Everything up to the backup still ran, on the data that was there.
    assert {"source/bravo", "exports", "backup_archive"} <= materialized(result)
    (failure,) = [e for e in result.all_events if e.event_type == dg.DagsterEventType.STEP_FAILURE]
    assert failure.step_key == "health"
    assert alerted_already([failure.step_key])
    assert not alerted_already(["exports", "health"]) and not alerted_already([])


def test_site_and_backup_run_when_configured(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "publish.sh"
    marker = tmp_path / "published"
    script.write_text(f"#!/bin/sh\ntouch {marker}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("CL_PUBLISH_SITE_SCRIPT", str(script))
    monkeypatch.setenv("CL_BACKUP_DIR", str(tmp_path / "backups"))
    result = run(ledger(settings))
    assert result.success and marker.exists()
    assert len(list((tmp_path / "backups").glob("ledger-*.tar.gz"))) == 1


def test_a_failed_site_build_fails_the_run_after_maintenance_and_backup(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "publish.sh"
    script.write_text("#!/bin/sh\necho 'pnpm build failed' >&2\nexit 1\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("CL_PUBLISH_SITE_SCRIPT", str(script))
    monkeypatch.setenv("CL_BACKUP_DIR", str(tmp_path / "backups"))
    result = run(ledger(settings))
    assert not result.success
    assert {"maintenance", "backup_archive"} <= materialized(result)
    assert len(list((tmp_path / "backups").glob("ledger-*.tar.gz"))) == 1
    (failure,) = [e for e in result.all_events if e.event_type == dg.DagsterEventType.STEP_FAILURE]
    user_failure = failure.step_failure_data.user_failure_data
    assert user_failure is not None and "site-failed" in str(user_failure.metadata)
