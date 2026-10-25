from datetime import UTC, datetime

import pyarrow as pa
from ledger_pipelines.arrow import TIMESTAMP, schema_for, to_table
from ledger_schemas import CrawlRun, Vulnerability


def test_vulnerability_schema() -> None:
    schema = schema_for(Vulnerability)
    assert schema.field("id").type == pa.string() and not schema.field("id").nullable
    assert schema.field("cve_id").nullable is False
    assert schema.field("published").type == TIMESTAMP and schema.field("published").nullable
    assert schema.field("kev_date_added").type == pa.date32()
    assert schema.field("kev_ransomware_use").type == pa.string()
    cwes = schema.field("cwe_ids")
    assert cwes.type == pa.list_(pa.field("element", pa.string(), nullable=False))
    prov = schema.field("provenance")
    assert pa.types.is_struct(prov.type) and not prov.nullable
    assert prov.type.field("confidence").type == pa.int64()


def test_to_table_round_trips() -> None:
    now = datetime(2026, 10, 24, tzinfo=UTC)
    run = CrawlRun(
        run_id="crawl:x:1",
        kind="crawl",
        source_id="x",
        plugin_version="1",
        started_at=now,
        finished_at=now,
        status="succeeded",
        documents=1,
        records=0,
    )
    (row,) = to_table(CrawlRun, [run]).to_pylist()
    assert CrawlRun.model_validate(row) == run
