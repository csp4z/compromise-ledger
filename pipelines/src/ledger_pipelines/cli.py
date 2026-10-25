"""The ``ledger`` command."""

import argparse
import sys

from ledger_crawl.registry import discover_crawlers
from ledger_schemas import CrawlRun

from ledger_pipelines.checks import Problem
from ledger_pipelines.config import Settings
from ledger_pipelines.notify import alert
from ledger_pipelines.runner import Runner, UnknownSourceError


def _report(run: CrawlRun) -> int:
    seconds = (run.finished_at - run.started_at).total_seconds()
    line = (
        f"{run.kind} {run.source_id}: {run.status} in {seconds:.1f}s, "
        f"{run.documents} document(s), {run.records} record(s)"
    )
    print(line if run.error is None else f"{line}\n  {run.error}", file=sys.stderr)
    return 0 if run.status == "succeeded" else 1


def _report_problems(settings: Settings, problems: list[Problem], *, notify: bool) -> int:
    for problem in problems:
        print(f"check failed: {problem}", file=sys.stderr)
    if not problems:
        print("checks passed", file=sys.stderr)
    if notify:
        alert(settings, problems)
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
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
    check = commands.add_parser("check", help="health checks over recent runs")
    check.add_argument("--notify", action="store_true", help="send alerts if checks fail")
    job = commands.add_parser("run", help="run a scheduled job")
    job.add_argument("job", choices=["daily"], help="daily: every step, then check and alert")
    args = parser.parse_args(argv)

    if args.command == "sources":
        for meta in sorted((c.meta for c in discover_crawlers().values()), key=lambda m: m.id):
            print(f"{meta.id}\t{meta.schedule}\t{meta.license}\t{meta.description}")
        return 0

    try:
        settings = Settings.from_env()
        runner = Runner(settings)
        if args.command == "check":
            problems = runner.check()
            return _report_problems(settings, problems, notify=args.notify)
        if args.command == "run":
            runs, problems = runner.run_daily()
            step_codes = [_report(r) for r in runs]
            check_code = _report_problems(settings, problems, notify=True)
            return max([check_code, *step_codes])
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
    except (UnknownSourceError, ValueError, NotImplementedError) as exc:
        print(f"ledger: {exc}", file=sys.stderr)
        return 2
    return _report(run)


if __name__ == "__main__":
    sys.exit(main())
