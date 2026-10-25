"""Writes a small sample export for tests and CI builds: ``make sample-exports``.

``python -m ledger_pipelines.sample SOURCE_EXPORTS_DIR OUT_DIR``. The sample keeps a few
vendors' KEV entries (and the CVEs they reference) plus the small summary tables whole, and is
written with the normal exporter, so its manifest and checksums are real.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from ledger_pipelines.export import ExportTable, Source, export

VENDORS = ("palo-alto-networks", "fortinet", "sonicwall", "microsoft", "cisco")
ENTRIES_PER_VENDOR = 8


def make_sample(source: Path, out: Path) -> None:
    manifest = json.loads((source / "datasets.json").read_text(encoding="utf-8"))
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    for name in {f["table"].removeprefix("gold.") for f in manifest["files"]}:
        con.register(name, pq.read_table(source / f"{name}.parquet"))
    placeholders = ", ".join("?" for _ in VENDORS)
    con.execute(
        f"""CREATE TABLE sample_kev AS SELECT * FROM kev_vendor_products
            WHERE vendor_slug IN ({placeholders})
            QUALIFY row_number() OVER (PARTITION BY vendor_slug
                                       ORDER BY kev_date_added DESC, cve_id) <= ?""",  # noqa: S608
        [*VENDORS, ENTRIES_PER_VENDOR],
    )
    queries = {
        "vulnerabilities": "SELECT * FROM vulnerabilities WHERE cve_id IN "
        "(SELECT cve_id FROM sample_kev) ORDER BY cve_id",
        "kev_vendor_products": "SELECT * FROM sample_kev ORDER BY kev_date_added DESC, cve_id",
        "vendors": f"SELECT * FROM vendors WHERE slug IN ({placeholders}) "  # noqa: S608
        "OR is_security_vendor ORDER BY kev_count DESC, slug",
        "security_vendor_summary": "SELECT * FROM security_vendor_summary",
        "security_vendor_kev_monthly": "SELECT * FROM security_vendor_kev_monthly",
        "unresolved_vendor_names": "SELECT * FROM unresolved_vendor_names",
    }
    tables = []
    for name, sql in queries.items():
        params = list(VENDORS) if "?" in sql else []
        snapshot = next(
            f["iceberg_snapshot_id"] for f in manifest["files"] if f["table"] == f"gold.{name}"
        )
        tables.append(ExportTable(name, con.execute(sql, params).to_arrow_table(), snapshot))
    sources = [
        Source(s["id"], s["description"], s["license"], s.get("attribution"))
        for s in manifest["sources"]
    ]
    export(tables, sources, out, generated_at=datetime.fromisoformat(manifest["generated_at"]))


if __name__ == "__main__":
    make_sample(Path(sys.argv[1]), Path(sys.argv[2]))
