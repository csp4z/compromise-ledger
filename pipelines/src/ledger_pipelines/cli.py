"""The ``ledger`` command."""

import argparse
import sys

from ledger_crawl.registry import discover_crawlers
from ledger_schemas import CrawlRun

from ledger_pipelines.config import Settings
from ledger_pipelines.runner import Runner, UnknownSourceError


def _report(run: CrawlRun) -> int:
    seconds = (run.finished_at - run.started_at).total_seconds()
    line = (
        f"{run.kind} {run.source_id}: {run.status} in {seconds:.1f}s, "
        f"{run.documents} document(s), {run.records} record(s)"
    )
    print(line if run.error is None else f"{line}\n  {run.error}", file=sys.stderr)
    return 0 if run.status == "succeeded" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ledger", description="Compromise Ledger pipelines.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sources", help="list registered clearnet crawlers")
    crawl = commands.add_parser("crawl", help="fetch a source into bronze")
    crawl.add_argument("source")
    parse = commands.add_parser("parse", help="parse a source's latest raw document into silver")
    parse.add_argument("source")
    commands.add_parser("resolve", help="map vendor names to seeds; rebuild vendors and products")
    args = parser.parse_args(argv)

    if args.command == "sources":
        for meta in sorted((c.meta for c in discover_crawlers().values()), key=lambda m: m.id):
            print(f"{meta.id}\t{meta.schedule}\t{meta.license}\t{meta.description}")
        return 0

    try:
        runner = Runner(Settings.from_env())
        if args.command == "crawl":
            run = runner.crawl(args.source)
        elif args.command == "parse":
            run = runner.parse(args.source)
        else:
            run = runner.resolve()
    except (UnknownSourceError, ValueError, NotImplementedError) as exc:
        print(f"ledger: {exc}", file=sys.stderr)
        return 2
    return _report(run)


if __name__ == "__main__":
    sys.exit(main())
