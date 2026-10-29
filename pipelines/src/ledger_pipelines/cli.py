"""The ``ledger`` command."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from ledger_crawl.registry import discover_crawlers
from ledger_schemas import CrawlRun

from ledger_pipelines.backup import backup
from ledger_pipelines.checks import Problem
from ledger_pipelines.config import Settings
from ledger_pipelines.lock import LockedError, exclusive
from ledger_pipelines.notify import alert
from ledger_pipelines.runner import Runner, UnknownSourceError

EXIT_LOCKED = 75  # EX_TEMPFAIL: another run holds the lock; try again later


def _log(line: str) -> None:
    # Unbuffered and immediate, so `tail -f` on the log shows each step as it happens.
    print(line, file=sys.stderr, flush=True)


def _status(run: CrawlRun) -> int:
    return 0 if run.status == "succeeded" else 1


def _report_problems(settings: Settings, problems: list[Problem], *, notify: bool) -> int:
    for problem in problems:
        _log(f"check failed: {problem}")
    if not problems:
        _log("checks passed")
    if notify:
        alert(settings, problems)
    return 1 if problems else 0


def _corrections(runner: Runner) -> int:
    missing = 0
    targets = runner.correction_targets()
    for correction, tables in targets:
        where = ", ".join(tables) if tables else "NOT FOUND"
        missing += not tables
        print(f"{correction.request_ref}\t{correction.action}\t{correction.target_id}\t{where}")
    _log(f"{len(targets)} correction(s), {missing} with no matching record")
    return 1 if missing else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ledger", description="Compromise Ledger pipelines.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sources", help="list registered clearnet crawlers")
    crawl = commands.add_parser("crawl", help="fetch a source into bronze")
    crawl.add_argument("source")
    parse = commands.add_parser("parse", help="parse a source's latest raw document into silver")
    parse.add_argument("source")
    commands.add_parser("resolve", help="map vendor names to seeds; rebuild vendors and products")
    build = commands.add_parser("build", help="build a layer")
    build.add_argument("layer", choices=["gold"])
    commands.add_parser("export", help="rebuild gold, then write the export files and manifest")
    commands.add_parser(
        "corrections", help="validate the corrections file and find each correction's target"
    )
    check = commands.add_parser("check", help="health checks over recent runs")
    check.add_argument("--notify", action="store_true", help="send alerts if checks fail")
    archive = commands.add_parser("backup", help="archive catalog, warehouse and raw blobs")
    archive.add_argument("dest", type=Path, help="directory for ledger-<time>.tar.gz archives")
    archive.add_argument("--keep", type=int, default=7, help="archives to keep (default 7)")
    job = commands.add_parser("run", help="run a scheduled job")
    job.add_argument("job", choices=["daily"], help="daily: every step, then check and alert")
    return parser


def _write(runner: Runner, settings: Settings, args: argparse.Namespace) -> int:
    """Commands that need the lock: every write, and backups. The caller holds it."""
    if args.command == "run":
        runs, problems = runner.run_daily()
        check_code = _report_problems(settings, problems, notify=True)
        return max([check_code, *(_status(r) for r in runs)])
    if args.command == "backup":
        archive = backup(settings, args.dest, now=datetime.now(UTC), keep=args.keep)
        _log(f"backup: wrote {archive} ({archive.stat().st_size} bytes)")
        return 0
    if args.command == "crawl":
        run = runner.crawl(args.source)
    elif args.command == "parse":
        run = runner.parse(args.source)
    elif args.command == "resolve":
        run = runner.resolve()
    elif args.command == "build":
        run = runner.build_gold()
    else:
        run = runner.export()
    return _status(run)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "sources":
        for meta in sorted((c.meta for c in discover_crawlers().values()), key=lambda m: m.id):
            print(f"{meta.id}\t{meta.schedule}\t{meta.license}\t{meta.description}")
        return 0

    try:
        settings = Settings.from_env()
        if args.command == "corrections":
            return _corrections(Runner(settings))
        if args.command == "check":
            problems = Runner(settings).check()
            return _report_problems(settings, problems, notify=args.notify)
        with exclusive(settings.data_dir):
            return _write(Runner(settings, progress=_log), settings, args)
    except LockedError as exc:
        _log(f"ledger: {exc}")
        return EXIT_LOCKED
    except (UnknownSourceError, ValueError, NotImplementedError) as exc:
        _log(f"ledger: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
