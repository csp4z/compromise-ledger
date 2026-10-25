import sqlite3
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ledger_pipelines.backup import backup
from ledger_pipelines.config import Settings
from ledger_pipelines.lakehouse import Lakehouse

NOW = datetime(2026, 10, 25, 3, 0, tzinfo=UTC)


def lake_with_data(settings: Settings) -> None:
    Lakehouse(settings).table("ops.crawl_runs")  # creates the catalog and a table
    (settings.data_dir / "raw" / "x").mkdir(parents=True)
    (settings.data_dir / "raw" / "x" / "blob").write_bytes(b"body")


def test_archive_holds_catalog_warehouse_and_raw(settings: Settings, tmp_path: Path) -> None:
    lake_with_data(settings)
    archive = backup(settings, tmp_path / "backups", now=NOW)
    assert archive.name == "ledger-20261025T030000Z.tar.gz"
    with tarfile.open(archive) as tar:
        names = tar.getnames()
        assert "catalog.db" in names and "raw/x/blob" in names
        assert any(n.startswith("warehouse/ops/") for n in names)
        tar.extract("catalog.db", tmp_path / "restore", filter="data")
    with sqlite3.connect(tmp_path / "restore" / "catalog.db") as db:
        tables = {r[0] for r in db.execute("SELECT table_name FROM iceberg_tables")}
    assert "crawl_runs" in tables


def test_keeps_only_the_newest(settings: Settings, tmp_path: Path) -> None:
    lake_with_data(settings)
    dest = tmp_path / "backups"
    for day in range(5):
        backup(settings, dest, now=NOW + timedelta(days=day), keep=3)
    (dest / "notes.txt").write_text("not an archive")
    backup(settings, dest, now=NOW + timedelta(days=5), keep=3)
    kept = sorted(p.name for p in dest.iterdir())
    assert kept == [
        "ledger-20261028T030000Z.tar.gz",
        "ledger-20261029T030000Z.tar.gz",
        "ledger-20261030T030000Z.tar.gz",
        "notes.txt",
    ]


def test_rejects_non_sqlite_catalogs(settings: Settings, tmp_path: Path) -> None:
    other = Settings.from_env({"CL_DATA_DIR": str(settings.data_dir), "CL_CATALOG_URI": "http://x"})
    with pytest.raises(ValueError, match="SQLite"):
        backup(other, tmp_path, now=NOW)
