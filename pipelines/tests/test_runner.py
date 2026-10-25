import dataclasses
import json
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from ledger_crawl import (
    CrawlContext,
    CrawlerMeta,
    FetchedDocument,
    ParseContext,
    Parser,
    ParserMeta,
    RateLimit,
)
from ledger_crawl.testing import Fixture, fixture_transport
from ledger_pipelines.config import Settings
from ledger_pipelines.lakehouse import Lakehouse
from ledger_pipelines.runner import Runner
from ledger_schemas import ProductMention, Provenance, Vulnerability
from pydantic import BaseModel

FEED = "https://data.example.org/feed.json"
PAN = ("CVE-2024-3400", "Palo Alto Networks", "PAN-OS")
FORTI = ("CVE-2024-21762", "Fortinet", "FortiOS")


class FakeCrawler:
    meta = CrawlerMeta(
        id="example",
        version="0.1.0",
        description="Fake snapshot source",
        schedule="0 6 * * *",
        rate_limit=RateLimit(requests=100, per_seconds=1),
        license="CC0-1.0",
        allowed_hosts=("data.example.org",),
        content_types=("application/json",),
    )

    def fetch(self, ctx: CrawlContext) -> Iterator[FetchedDocument]:
        yield ctx.get(FEED)


class FakeParser:
    """Body: a JSON list of [cve_id, vendor, product]."""

    meta = ParserMeta(id="example", version="0.1.0", source_id="example", confidence=90)

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


def feed(*entries: tuple[str, str, str]) -> Fixture:
    return Fixture(json.dumps([list(e) for e in entries]).encode())


MakeRunner = Callable[..., Runner]


@pytest.fixture
def make_runner(settings: Settings) -> MakeRunner:
    def make(
        routes: dict[str, Fixture],
        parser: Parser | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> Runner:
        return Runner(
            settings,
            crawlers={"example": FakeCrawler()},
            parsers={"example": parser or FakeParser()},
            transport=fixture_transport(routes),
            clock=clock,
        )

    return make


def rows(lake: Lakehouse, table: str) -> list[dict[str, Any]]:
    return lake.table(table).scan().to_arrow().to_pylist()


def test_crawl_stores_blob_bronze_row_and_run(make_runner: MakeRunner) -> None:
    runner = make_runner({FEED: feed(PAN)})
    run = runner.crawl("example")
    assert run.status == "succeeded" and run.documents == 1
    (raw,) = rows(runner.lake, "bronze.raw_documents")
    assert runner.blobs.get(f"raw/example/{raw['id'][:2]}/{raw['id']}") == feed(PAN).body
    (recorded,) = rows(runner.lake, "ops.crawl_runs")
    assert recorded["run_id"] == run.run_id


def test_second_crawl_gets_last_success(
    make_runner: MakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    times = iter(datetime(2026, 10, d, tzinfo=UTC) for d in (1, 1, 2, 2))
    runner = make_runner({FEED: feed(PAN)}, clock=lambda: next(times))
    seen: list[datetime | None] = []

    def spy(*args: Any, **kwargs: Any) -> CrawlContext:
        seen.append(kwargs["last_success"])
        return CrawlContext(*args, **kwargs)

    monkeypatch.setattr("ledger_pipelines.runner.CrawlContext", spy)
    runner.crawl("example")
    runner.crawl("example")
    assert seen == [None, datetime(2026, 10, 1, tzinfo=UTC)]


def test_failed_crawl_is_recorded(make_runner: MakeRunner) -> None:
    runner = make_runner({FEED: Fixture(b"", status=503)})
    run = runner.crawl("example")
    assert run.status == "failed" and "503" in (run.error or "")
    assert not runner.lake.exists("bronze.raw_documents")
    assert runner.lake.last_successful_run("crawl", "example") is None


def test_parse_writes_silver(make_runner: MakeRunner) -> None:
    runner = make_runner({FEED: feed(PAN, FORTI)})
    runner.crawl("example")
    run = runner.parse("example")
    assert run.status == "succeeded" and run.records == 4
    vulns = rows(runner.lake, "silver.vulnerabilities")
    assert sorted(v["cve_id"] for v in vulns) == ["CVE-2024-21762", "CVE-2024-3400"]
    assert Vulnerability.model_validate(vulns[0]).provenance.parser_id == "example"
    assert len(rows(runner.lake, "silver.product_mentions")) == 2


def test_reparse_replaces_only_this_parsers_rows(make_runner: MakeRunner) -> None:
    first = make_runner({FEED: feed(PAN, FORTI)})
    first.crawl("example")
    first.parse("example")

    # Another source's row in the same table must survive.
    provenance = rows(first.lake, "silver.vulnerabilities")[0]["provenance"]
    other = Vulnerability(
        cve_id="CVE-2023-20198",
        provenance=Provenance.model_validate({**provenance, "parser_id": "other"}),
    )
    first.lake.append("silver.vulnerabilities", [other])

    # The source drops FORTI.
    second = make_runner({FEED: feed(PAN)})
    second.crawl("example")
    second.parse("example")
    by_parser = sorted(
        (v["provenance"]["parser_id"], v["cve_id"])
        for v in rows(second.lake, "silver.vulnerabilities")
    )
    assert by_parser == [("example", "CVE-2024-3400"), ("other", "CVE-2023-20198")]
    assert len(rows(second.lake, "silver.product_mentions")) == 1


def test_parse_failure_writes_nothing(make_runner: MakeRunner) -> None:
    runner = make_runner({FEED: feed(PAN, ("not-a-cve", "X", "Y"))})
    runner.crawl("example")
    run = runner.parse("example")
    assert run.status == "failed" and "cve_id" in (run.error or "")
    assert not runner.lake.exists("silver.vulnerabilities")


def test_parse_before_crawl_fails(make_runner: MakeRunner) -> None:
    run = make_runner({}).parse("example")
    assert run.status == "failed" and "run a crawl first" in (run.error or "")


def test_rejects_records_attributed_to_another_parser(make_runner: MakeRunner) -> None:
    class Mislabeled(FakeParser):
        def parse(self, body: bytes, ctx: ParseContext) -> Iterable[BaseModel]:
            prov = ctx.provenance().model_copy(update={"parser_id": "someone-else"})
            yield Vulnerability(cve_id="CVE-2024-3400", provenance=prov)

    runner = make_runner({FEED: feed(PAN)}, parser=Mislabeled())
    runner.crawl("example")
    run = runner.parse("example")
    assert run.status == "failed" and "lacks provenance" in (run.error or "")


def test_resolve_builds_vendors_products_and_unresolved(
    make_runner: MakeRunner, settings: Settings, tmp_path: Path
) -> None:
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    (seeds / "vendors.csv").write_text(
        "slug,name,is_security_vendor,source,note\n"
        "palo-alto-networks,Palo Alto Networks,true,https://www.paloaltonetworks.com/,x\n",
        encoding="utf-8",
    )
    (seeds / "vendor_aliases.csv").write_text("alias,vendor_slug,note\n", encoding="utf-8")
    runner = make_runner({FEED: feed(PAN, FORTI)})
    runner.settings = dataclasses.replace(settings, seeds_dir=seeds)
    runner.crawl("example")
    runner.parse("example")
    run = runner.resolve()
    assert run.status == "succeeded" and run.documents == 2
    assert [v["slug"] for v in rows(runner.lake, "silver.vendors")] == ["palo-alto-networks"]
    assert [p["slug"] for p in rows(runner.lake, "silver.products")] == ["pan-os"]
    assert len(rows(runner.lake, "silver.relationships")) == 1
    assert [u["vendor_name"] for u in rows(runner.lake, "ops.unresolved_vendor_names")] == [
        "Fortinet"
    ]
    # Re-running replaces rather than duplicates, and a later parse leaves resolution intact.
    runner.resolve()
    runner.parse("example")
    assert len(rows(runner.lake, "silver.products")) == 1


def test_resolve_with_bad_seeds_fails_cleanly(make_runner: MakeRunner, tmp_path: Path) -> None:
    runner = make_runner({})
    runner.settings = dataclasses.replace(runner.settings, seeds_dir=tmp_path / "missing")
    run = runner.resolve()
    assert run.status == "failed" and "vendors.csv" in (run.error or "")


def test_export_end_to_end(make_runner: MakeRunner, settings: Settings) -> None:
    runner = make_runner({FEED: feed(PAN, FORTI)})
    runner.crawl("example")
    runner.parse("example")
    runner.resolve()
    run = runner.export()
    assert run.status == "succeeded", run.error
    manifest = json.loads((settings.exports_dir / "datasets.json").read_text())
    assert [s["id"] for s in manifest["sources"]] == ["example", "vendor-seeds"]
    snapshot_ids = {f["iceberg_snapshot_id"] for f in manifest["files"]}
    assert None not in snapshot_ids
    kinds = [r["kind"] for r in rows(runner.lake, "ops.crawl_runs")]
    assert kinds.count("build") == 1 and kinds.count("export") == 1
    # A second export rebuilds gold in place.
    assert runner.export().status == "succeeded"
