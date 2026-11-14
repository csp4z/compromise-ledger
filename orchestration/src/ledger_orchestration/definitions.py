"""The daily pipeline as Dagster assets (ADR 0007).

Every step is the same plain function the ``ledger`` CLI calls; this module only arranges them:

    sources (one asset each, after the sources they name in CrawlerMeta.after)
      -> vendor_resolution -> exports -> site -> maintenance -> backup -> health

Two properties of ``ledger run daily`` are kept on purpose:

- **A failing step doesn't stop the rest.** Steps record their failure instead of raising, so
  later steps still run on the last good data. A source's failure shows as a failed ``healthy``
  check on its asset; ``health``, the last asset, runs every check, sends the alerts, and fails
  the run if anything broke.
- **One writer.** The SQLite catalog allows a single writer (ADR 0003), so the whole run holds
  the ledger lock and runs in one process, one step at a time, and Dagster runs one job at a time
  (``deploy/dagster/dagster.yaml``).
"""

import os
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import dagster as dg
from ledger_crawl import Crawler
from ledger_crawl.registry import discover_crawlers
from ledger_pipelines.backup import backup
from ledger_pipelines.checks import Problem
from ledger_pipelines.config import Settings
from ledger_pipelines.inputs import crawl_order
from ledger_pipelines.lock import exclusive
from ledger_pipelines.notify import alert
from ledger_pipelines.runner import Runner
from ledger_schemas import CrawlRun

SCHEDULE = "30 4 * * *"  # 04:30 UTC, as the supercronic job ran
HISTORY_DAYS = 7  # ADR 0006
DEFAULT_BACKUP_KEEP = 7
# Set in the container: the script that rebuilds the site and switches to it atomically. Unset
# (local runs), the site step is skipped.
PUBLISH_SITE_ENV = "CL_PUBLISH_SITE_SCRIPT"
BACKUP_DIR_ENV = "CL_BACKUP_DIR"
BACKUP_KEEP_ENV = "CL_BACKUP_KEEP"


@dataclass
class Ledger:
    """What every step needs: the runner, its settings, and the failures of steps that aren't
    recorded in ``ops.crawl_runs`` (site, maintenance, backup), for the final health check."""

    runner: Runner
    settings: Settings
    failures: list[Problem] = field(default_factory=list[Problem])

    def fail(self, step: str, message: str) -> None:
        self.failures.append(Problem(step, f"{step}-failed", message[:2000]))


@dg.resource(description="The ledger runner, holding the single-writer lock for the whole run.")
def ledger_resource(_: dg.InitResourceContext) -> Iterator[Ledger]:
    settings = Settings.from_env()
    log = dg.get_dagster_logger()
    with exclusive(settings.data_dir):
        yield Ledger(Runner(settings, progress=log.info), settings)


def asset_name(source_id: str) -> str:
    """Asset key names allow letters, digits and underscores only."""
    return source_id.replace("-", "_")


def source_key(source_id: str) -> dg.AssetKey:
    return dg.AssetKey(["source", asset_name(source_id)])


def _run_metadata(run: CrawlRun) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        f"{run.kind}_status": run.status,
        f"{run.kind}_documents": run.documents,
        f"{run.kind}_records": run.records,
        f"{run.kind}_seconds": round((run.finished_at - run.started_at).total_seconds(), 1),
    }
    if run.error:
        metadata[f"{run.kind}_error"] = dg.MetadataValue.text(run.error)
    return metadata


def _source_asset(source_id: str, crawler: Crawler) -> dg.AssetsDefinition:
    key = source_key(source_id)
    meta = crawler.meta

    @dg.asset(
        key=key,
        group_name="sources",
        deps=[source_key(s) for s in meta.after],
        description=meta.description,
        required_resource_keys={"ledger"},
        check_specs=[dg.AssetCheckSpec("healthy", asset=key, description="ledger check")],
        metadata={
            "license": meta.license,
            "inputs": ", ".join(meta.inputs) or "none",
            "rate_limit": f"{meta.rate_limit.requests} per {meta.rate_limit.per_seconds:g}s",
            "max_age_hours": meta.max_age_hours,
        },
        kinds={"python", "iceberg"},
    )
    def source(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
        ledger: Ledger = context.resources.ledger
        crawl = ledger.runner.crawl(source_id)
        metadata = _run_metadata(crawl)
        if crawl.status == "succeeded" and crawl.documents:
            metadata |= _run_metadata(ledger.runner.parse(source_id))
        problems = [p for p in ledger.runner.check() if p.source_id == source_id]
        return dg.MaterializeResult(
            metadata=metadata,
            check_results=[
                dg.AssetCheckResult(
                    check_name="healthy",
                    passed=not problems,
                    severity=dg.AssetCheckSeverity.ERROR,
                    metadata={"problems": "\n".join(str(p) for p in problems) or "none"},
                )
            ],
        )

    return source


def build_assets(crawlers: Mapping[str, Crawler]) -> list[dg.AssetsDefinition]:
    """One asset per source, then the pipeline steps. Sources keep the CLI's run order."""
    sources = [_source_asset(s, crawlers[s]) for s in crawl_order(crawlers)]
    source_keys = [source_key(s) for s in crawl_order(crawlers)]

    @dg.asset(
        group_name="pipeline",
        deps=source_keys,
        required_resource_keys={"ledger"},
        description="Map source vendor names to the curated vendors; rebuild vendors and products.",
        kinds={"python", "iceberg"},
    )
    def vendor_resolution(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
        return dg.MaterializeResult(
            metadata=_run_metadata(context.resources.ledger.runner.resolve())
        )

    @dg.asset(
        group_name="pipeline",
        deps=[vendor_resolution],
        required_resource_keys={"ledger"},
        description="Apply corrections, build gold, write Parquet, CSV, JSON and datasets.json.",
        kinds={"duckdb", "parquet"},
    )
    def exports(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
        return dg.MaterializeResult(
            metadata=_run_metadata(context.resources.ledger.runner.export())
        )

    @dg.asset(
        group_name="publish",
        deps=[exports],
        required_resource_keys={"ledger"},
        description="Rebuild the static site from the export and switch to it atomically.",
        kinds={"svelte"},
    )
    def site(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
        ledger: Ledger = context.resources.ledger
        script = os.environ.get(PUBLISH_SITE_ENV)
        if not script:
            return dg.MaterializeResult(metadata={"published": False, "reason": "not configured"})
        if not (ledger.settings.exports_dir / "datasets.json").exists():
            ledger.fail("site", "no export to build from")
            return dg.MaterializeResult(metadata={"published": False, "reason": "no export"})
        result = subprocess.run(  # noqa: S603 - a fixed script path from the container's environment
            [script], capture_output=True, text=True, check=False
        )
        context.log.info(result.stdout[-4000:])
        if result.returncode != 0:
            ledger.fail("site", result.stderr[-2000:] or f"exit status {result.returncode}")
        return dg.MaterializeResult(metadata={"published": result.returncode == 0})

    @dg.asset(
        group_name="publish",
        deps=[site],
        required_resource_keys={"ledger"},
        description=f"Expire bronze, silver and ops history older than {HISTORY_DAYS} days.",
        kinds={"iceberg"},
    )
    def maintenance(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
        ledger: Ledger = context.resources.ledger
        try:
            cutoff = datetime.now(UTC) - timedelta(days=HISTORY_DAYS)
            expired, deleted = ledger.runner.lake.expire_snapshots(cutoff)
        except Exception as exc:  # recorded for the health step, like every other step
            ledger.fail("maintain", f"{type(exc).__name__}: {exc}")
            return dg.MaterializeResult(metadata={"succeeded": False})
        return dg.MaterializeResult(
            metadata={"snapshots_expired": expired, "files_deleted": deleted}
        )

    @dg.asset(
        group_name="publish",
        deps=[maintenance],
        required_resource_keys={"ledger"},
        description="Archive the catalog, warehouse and raw blobs.",
        kinds={"python"},
    )
    def backup_archive(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
        ledger: Ledger = context.resources.ledger
        directory = os.environ.get(BACKUP_DIR_ENV)
        if not directory:
            return dg.MaterializeResult(metadata={"written": False, "reason": "not configured"})
        try:
            keep = int(os.environ.get(BACKUP_KEEP_ENV, DEFAULT_BACKUP_KEEP))
            archive = backup(ledger.settings, Path(directory), now=datetime.now(UTC), keep=keep)
        except Exception as exc:
            ledger.fail("backup", f"{type(exc).__name__}: {exc}")
            return dg.MaterializeResult(metadata={"written": False})
        return dg.MaterializeResult(
            metadata={"archive": archive.name, "bytes": archive.stat().st_size}
        )

    @dg.asset(
        group_name="publish",
        deps=[backup_archive],
        required_resource_keys={"ledger"},
        description="Run every health check, send alerts, and fail the run if anything broke.",
    )
    def health(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
        ledger: Ledger = context.resources.ledger
        problems = [*ledger.runner.check(), *ledger.failures]
        # Also pings healthchecks.io, the dead-man's switch, with the result.
        undelivered = alert(ledger.settings, problems)
        if problems:
            raise dg.Failure(
                description=f"{len(problems)} health check(s) failed",
                metadata={"problems": "\n".join(str(p) for p in problems)},
            )
        return dg.MaterializeResult(metadata={"alerts_undelivered": len(undelivered)})

    return [*sources, vendor_resolution, exports, site, maintenance, backup_archive, health]


def alerted_already(failed_steps: list[str]) -> bool:
    """A run that failed only in ``health`` has already sent its alerts."""
    return bool(failed_steps) and all(step == "health" for step in failed_steps)


@dg.run_failure_sensor(
    description="Alert when a run fails before its health step can.",
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def alert_on_run_failure(context: dg.RunFailureSensorContext) -> None:
    """A run that dies early (the lock is taken, a bug) never reaches ``health``. Alert anyway;
    the healthchecks.io failure ping also stops the dead-man's switch from waiting two hours."""
    failed = [e.step_key for e in context.get_step_failure_events() if e.step_key]
    if alerted_already(failed):
        return
    message = context.failure_event.message or "the run failed"
    alert(Settings.from_env(), [Problem("dagster", "run-failed", message[:2000])])


def build_definitions(crawlers: Mapping[str, Crawler] | None = None) -> dg.Definitions:
    assets = build_assets(crawlers if crawlers is not None else discover_crawlers())
    daily = dg.define_asset_job(
        "daily",
        selection=dg.AssetSelection.assets(*assets),
        executor_def=dg.in_process_executor,
        description="Every source, then resolution, exports, the site, maintenance and backup.",
    )
    return dg.Definitions(
        assets=assets,
        jobs=[daily],
        schedules=[
            dg.ScheduleDefinition(
                job=daily,
                cron_schedule=SCHEDULE,
                execution_timezone="UTC",
                default_status=dg.DefaultScheduleStatus.RUNNING,
            )
        ],
        sensors=[alert_on_run_failure],
        resources={"ledger": ledger_resource},
        # Every job, including the one behind the UI's "Materialize" button, runs its steps in one
        # process: the ledger lock admits one writer, and parallel steps would fail on it.
        executor=dg.in_process_executor,
    )


defs = build_definitions()
