"""Runs one crawl or parse for a source and records it in ``ops.crawl_runs``.

Pipeline steps are plain functions so Dagster can wrap them later (ADR 0002).
"""

from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

import httpx
from ledger_crawl import CrawlContext, Crawler, ParseContext, Parser
from ledger_crawl.registry import discover_crawlers, discover_parsers
from ledger_schemas import Correction, CrawlRun, ProductMention, RawDocument
from ledger_schemas.ops import RunKind
from pydantic import BaseModel

from ledger_pipelines import __version__
from ledger_pipelines.blobs import BlobStore, open_blob_store
from ledger_pipelines.checks import Problem, check
from ledger_pipelines.config import Settings
from ledger_pipelines.corrections import apply_corrections
from ledger_pipelines.export import ExportTable, Source, export, verify
from ledger_pipelines.gold import build_gold, gold_files
from ledger_pipelines.lakehouse import PARSER_TABLES, TABLES, Lakehouse
from ledger_pipelines.resolve import (
    RESOLVER_ID,
    RESOLVER_VERSION,
    SEEDS_LICENSE,
    load_seeds,
    resolve,
)

MAX_ERROR_CHARS = 2000


class UnknownSourceError(LookupError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:MAX_ERROR_CHARS]


class Runner:
    def __init__(
        self,
        settings: Settings,
        *,
        lake: Lakehouse | None = None,
        blobs: BlobStore | None = None,
        crawlers: Mapping[str, Crawler] | None = None,
        parsers: Mapping[str, Parser] | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.settings = settings
        self.lake = lake or Lakehouse(settings)
        self.blobs = blobs or open_blob_store(settings)
        self.crawlers = crawlers if crawlers is not None else discover_crawlers()
        self.parsers = parsers if parsers is not None else discover_parsers()
        self._transport = transport
        self._clock = clock

    def _crawler(self, source_id: str) -> Crawler:
        try:
            return self.crawlers[source_id]
        except KeyError:
            raise UnknownSourceError(f"no clearnet crawler named {source_id!r}") from None

    def _parser(self, source_id: str) -> Parser:
        matches = [p for p in self.parsers.values() if p.meta.source_id == source_id]
        if len(matches) != 1:
            raise UnknownSourceError(f"expected one parser for {source_id!r}, found {len(matches)}")
        return matches[0]

    def _record(
        self,
        kind: RunKind,
        source_id: str,
        version: str,
        started: datetime,
        *,
        documents: int,
        records: int = 0,
        error: str | None = None,
    ) -> CrawlRun:
        run = CrawlRun(
            run_id=f"{kind}:{source_id}:{started:%Y%m%dT%H%M%S.%fZ}",
            kind=kind,
            source_id=source_id,
            plugin_version=version,
            started_at=started,
            finished_at=self._clock(),
            status="failed" if error else "succeeded",
            documents=documents,
            records=records,
            error=error,
        )
        self.lake.append("ops.crawl_runs", [run])
        return run

    def crawl(self, source_id: str) -> CrawlRun:
        """Fetch documents, store each body as a blob, then append their bronze rows."""
        crawler = self._crawler(source_id)
        previous = self.lake.last_successful_run("crawl", source_id)
        started = self._clock()
        fetched: list[RawDocument] = []
        error = None
        try:
            with CrawlContext(
                crawler.meta,
                contact=self.settings.crawler_contact,
                last_success=previous.started_at if previous else None,
                transport=self._transport,
            ) as ctx:
                for doc in crawler.fetch(ctx):
                    # Blob first, so a bronze row never points at a missing body.
                    self.blobs.put(doc.raw.blob_key, doc.body)
                    fetched.append(doc.raw)
        except Exception as exc:
            error = _describe(exc)
        # Documents fetched before a failure are real and kept.
        self.lake.append("bronze.raw_documents", fetched)
        return self._record(
            "crawl", source_id, crawler.meta.version, started, documents=len(fetched), error=error
        )

    def parse(self, source_id: str) -> CrawlRun:
        """Parse the source's latest raw document and replace the parser's silver rows.

        Phase 1 sources publish full snapshots, so each parse replaces everything the parser
        wrote before; rows for entries the source dropped disappear too. Nothing is written
        unless the whole document parses.
        """
        parser = self._parser(source_id)
        crawler = self._crawler(source_id)
        started = self._clock()
        try:
            raw = self.lake.latest_raw_document(source_id)
            if raw is None:
                raise LookupError(f"no raw documents for {source_id!r}; run a crawl first")
            ctx = ParseContext(parser=parser.meta, raw=raw, license=crawler.meta.license)
            by_table: dict[str, list[BaseModel]] = defaultdict(list)
            for record in parser.parse(self.blobs.get(raw.blob_key), ctx):
                by_table[self._route(record, parser, raw)].append(record)
        except Exception as exc:
            return self._record(
                "parse", source_id, parser.meta.version, started, documents=0, error=_describe(exc)
            )
        for name in PARSER_TABLES.values():
            if by_table.get(name) or self.lake.exists(name):
                self.lake.replace_source(name, parser.meta.id, by_table.get(name, []))
        return self._record(
            "parse",
            source_id,
            parser.meta.version,
            started,
            documents=1,
            records=sum(len(rows) for rows in by_table.values()),
        )

    def resolve(self) -> CrawlRun:
        """Rebuild vendors, products, and relationships from all mentions and the seeds."""
        started = self._clock()
        try:
            seeds = load_seeds(self.settings.seeds_dir)
            mentions = []
            if self.lake.exists("silver.product_mentions"):
                table = self.lake.table("silver.product_mentions")
                mentions = [
                    ProductMention.model_validate(row)
                    for row in table.scan().to_arrow().to_pylist()
                ]
            result = resolve(mentions, seeds, built_at=started)
        except Exception as exc:
            return self._record(
                "resolve",
                RESOLVER_ID,
                RESOLVER_VERSION,
                started,
                documents=0,
                error=_describe(exc),
            )
        self.lake.replace_source("silver.vendors", RESOLVER_ID, result.vendors)
        self.lake.replace_source("silver.products", RESOLVER_ID, result.products)
        self.lake.replace_source("silver.relationships", RESOLVER_ID, result.relationships)
        self.lake.replace_all("ops.unresolved_vendor_names", result.unresolved)
        return self._record(
            "resolve",
            RESOLVER_ID,
            RESOLVER_VERSION,
            started,
            documents=len(mentions),
            records=len(result.vendors) + len(result.products) + len(result.relationships),
        )

    def build_gold(self) -> CrawlRun:
        """Apply corrections to silver, then rebuild every gold table."""
        started = self._clock()
        try:
            silver = {name: self.lake.read(name) for name in TABLES if name.startswith("silver.")}
            corrections = [
                Correction.model_validate(row)
                for row in silver.pop("silver.corrections").to_pylist()
            ]
            inputs = apply_corrections(silver, corrections)
            inputs["ops.unresolved_vendor_names"] = self.lake.read("ops.unresolved_vendor_names")
            gold = build_gold(inputs)
            for name, table in gold.items():
                self.lake.write_gold(name, table)
        except Exception as exc:
            return self._record(
                "build", "gold", __version__, started, documents=0, error=_describe(exc)
            )
        return self._record(
            "build",
            "gold",
            __version__,
            started,
            documents=len(corrections),
            records=sum(t.num_rows for t in gold.values()),
        )

    def export(self) -> CrawlRun:
        """Rebuild gold (so corrections are always applied), then write the export files."""
        build = self.build_gold()
        started = self._clock()
        if build.status == "failed":
            error = f"gold build failed: {build.error}"
            return self._record("export", "export", __version__, started, documents=0, error=error)
        try:
            tables = []
            for name, _ in gold_files():
                table = self.lake.catalog.load_table(f"gold.{name}")
                snapshot = table.current_snapshot()
                tables.append(
                    ExportTable(
                        name=name,
                        table=table.scan().to_arrow(),
                        snapshot_id=snapshot.snapshot_id if snapshot else None,
                    )
                )
            manifest = export(
                tables, self._sources(), self.settings.exports_dir, generated_at=started
            )
            problems = verify(self.settings.exports_dir)
            if problems:
                raise ValueError("; ".join(problems))
        except Exception as exc:
            return self._record(
                "export", "export", __version__, started, documents=0, error=_describe(exc)
            )
        return self._record(
            "export",
            "export",
            __version__,
            started,
            documents=len(manifest["files"]),
            records=sum(t.table.num_rows for t in tables),
        )

    def check(self) -> list[Problem]:
        return check(self.lake.runs(), self.crawlers, now=self._clock())

    def run_daily(self) -> tuple[list[CrawlRun], list[Problem]]:
        """Crawl and parse every clearnet source, then resolve, export, and check.

        A failing source doesn't stop the others, and later steps still run, so the export
        keeps the last good data for that source and the check reports what broke.
        """
        runs: list[CrawlRun] = []
        for source_id in sorted(self.crawlers):
            crawl = self.crawl(source_id)
            runs.append(crawl)
            if crawl.status == "succeeded" and crawl.documents:
                runs.append(self.parse(source_id))
        runs.append(self.resolve())
        runs.append(self.export())
        return runs, self.check()

    def _sources(self) -> list[Source]:
        crawled = set(self.lake.read("bronze.raw_documents").column("source_id").to_pylist())
        sources = [
            Source(id=c.meta.id, description=c.meta.description, license=c.meta.license)
            for c in sorted(self.crawlers.values(), key=lambda c: c.meta.id)
            if c.meta.id in crawled
        ]
        seeds = "Curated vendor list and aliases (data/seeds/)"
        return [*sources, Source(id="vendor-seeds", description=seeds, license=SEEDS_LICENSE)]

    @staticmethod
    def _route(record: BaseModel, parser: Parser, raw: RawDocument) -> str:
        table = PARSER_TABLES.get(type(record))
        if table is None:
            raise TypeError(f"parser emitted {type(record).__name__}, which has no silver table")
        provenance = getattr(record, "provenance", None)
        # replace_source keys on parser_id, so a record attributed elsewhere would corrupt it.
        if provenance is None or provenance.parser_id != parser.meta.id:
            raise ValueError(f"{type(record).__name__} lacks provenance from {parser.meta.id!r}")
        if provenance.raw_document_id != raw.id:
            raise ValueError(f"{type(record).__name__} cites a different raw document")
        return table
