from datetime import UTC, datetime, timedelta
from pathlib import Path

from ledger_pipelines.arrow import schema_for
from ledger_pipelines.config import Settings
from ledger_pipelines.lakehouse import METADATA_PROPERTIES, Lakehouse
from ledger_schemas import UnresolvedVendorName

TABLE = "ops.unresolved_vendor_names"
LATER = datetime.now(UTC) + timedelta(days=1)


def names(*vendors: str) -> list[UnresolvedVendorName]:
    return [
        UnresolvedVendorName(vendor_name=v, mentions=1, parser_ids=["example"]) for v in vendors
    ]


def files(settings: Settings, suffix: str) -> list[Path]:
    return sorted((settings.data_dir / "warehouse").rglob(f"*{suffix}"))


def test_expiry_keeps_the_current_snapshot_and_deletes_unused_files(settings: Settings) -> None:
    lake = Lakehouse(settings)
    for vendor in ("Acme", "Globex", "Initech"):
        lake.replace_all(TABLE, names(vendor))
    assert len(lake.table(TABLE).snapshots()) > 1

    expired, deleted = lake.expire_snapshots(LATER)

    table = lake.table(TABLE)
    assert expired > 0 and deleted > 0
    assert len(table.snapshots()) == 1
    assert lake.read(TABLE).column("vendor_name").to_pylist() == ["Initech"]
    assert len(files(settings, ".parquet")) == 1
    # Nothing left on disk that the current snapshot doesn't use.
    assert lake.expire_snapshots(LATER) == (0, 0)


def test_recent_snapshots_are_kept(settings: Settings) -> None:
    lake = Lakehouse(settings)
    lake.replace_all(TABLE, names("Acme"))
    lake.replace_all(TABLE, names("Globex"))
    before = len(lake.table(TABLE).snapshots())

    assert lake.expire_snapshots(datetime.now(UTC) - timedelta(days=7)) == (0, 0)
    assert len(lake.table(TABLE).snapshots()) == before


def test_old_metadata_files_are_deleted(settings: Settings) -> None:
    lake = Lakehouse(settings)
    for i in range(15):
        lake.replace_all(TABLE, names(f"Vendor {i}"))
    assert len(files(settings, ".metadata.json")) <= 11


def test_existing_tables_get_the_metadata_properties(settings: Settings) -> None:
    lake = Lakehouse(settings)
    lake.catalog.create_namespace_if_not_exists("ops")
    lake.catalog.create_table(TABLE, schema=schema_for(UnresolvedVendorName))
    lake.append(TABLE, names("Acme"))

    lake.expire_snapshots(LATER)

    properties = lake.table(TABLE).properties
    assert all(properties.get(k) == v for k, v in METADATA_PROPERTIES.items())
