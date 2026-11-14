"""Iceberg tables through PyIceberg's SQL catalog (ADR 0003)."""

import warnings
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime

import pyarrow as pa
from ledger_schemas import (
    BreachNotice,
    Correction,
    CrawlRun,
    CveCount,
    EpssScore,
    Incident,
    Organization,
    Product,
    ProductMention,
    RawDocument,
    Relationship,
    ThirdPartyIncident,
    UnresolvedVendorName,
    Vendor,
    Vulnerability,
)
from pydantic import BaseModel
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.expressions import AlwaysTrue, And, BooleanExpression, EqualTo
from pyiceberg.manifest import ManifestFile
from pyiceberg.table import Table
from pyiceberg.table.snapshots import Snapshot

from ledger_pipelines.arrow import schema_for, to_table
from ledger_pipelines.config import Settings

TABLES: dict[str, type[BaseModel]] = {
    "bronze.raw_documents": RawDocument,
    "silver.vendors": Vendor,
    "silver.products": Product,
    "silver.vulnerabilities": Vulnerability,
    "silver.relationships": Relationship,
    "silver.product_mentions": ProductMention,
    "silver.cve_counts": CveCount,
    "silver.organizations": Organization,
    "silver.incidents": Incident,
    "silver.third_party_incidents": ThirdPartyIncident,
    "silver.epss_scores": EpssScore,
    "silver.breach_notices": BreachNotice,
    "silver.corrections": Correction,
    "ops.crawl_runs": CrawlRun,
    "ops.unresolved_vendor_names": UnresolvedVendorName,
}

# Keep only the last few metadata.json files; each one lists every snapshot (ADR 0006).
METADATA_PROPERTIES = {
    "write.metadata.delete-after-commit.enabled": "true",
    "write.metadata.previous-versions-max": "10",
}

# Where parser output goes. Corrections and third-party marks are curated files loaded before
# each gold build, never parser output.
PARSER_TABLES: dict[type[BaseModel], str] = {
    model: name
    for name, model in TABLES.items()
    if name.startswith("silver.") and model not in (Correction, ThirdPartyIncident)
}


@contextmanager
def _quiet_empty_delete() -> Iterator[None]:
    """Silence PyIceberg's warning when an overwrite or delete finds nothing to remove.

    That is expected on a source's first write to a shared table, or when a table was empty.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "Delete operation did not match any records")
        yield


def _eq(column: str, value: str) -> BooleanExpression:
    # PyIceberg's predicates are Pydantic models whose __init__ pyright can't see.
    return EqualTo(column, value)  # pyright: ignore[reportCallIssue]


class _SnapshotFiles:
    """Every file a set of snapshots uses, reading each manifest once.

    Appends reuse earlier manifests, so a table with n snapshots has about n manifests, not n².
    """

    def __init__(self, table: Table) -> None:
        self._io = table.io
        self._manifests: dict[str, set[str]] = {}

    def of(self, snapshots: Iterable[Snapshot]) -> set[str]:
        paths: set[str] = set()
        for snapshot in snapshots:
            paths.add(snapshot.manifest_list)
            for manifest in snapshot.manifests(self._io):
                paths.add(manifest.manifest_path)
                paths |= self._data_files(manifest)
        return paths

    def _data_files(self, manifest: ManifestFile) -> set[str]:
        files = self._manifests.get(manifest.manifest_path)
        if files is None:
            # Live entries only. A carried-over manifest can still list a file as deleted; that
            # snapshot doesn't read it, and counting it would keep the file forever.
            entries = manifest.fetch_manifest_entry(self._io, discard_deleted=True)
            files = {entry.data_file.file_path for entry in entries}
            self._manifests[manifest.manifest_path] = files
        return files


class Lakehouse:
    def __init__(self, settings: Settings) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = SqlCatalog("ledger", uri=settings.catalog_uri, warehouse=settings.warehouse)

    def exists(self, name: str) -> bool:
        return self.catalog.table_exists(name)

    def table(self, name: str) -> Table:
        """Open a table, creating it or adding new model fields to it as needed."""
        schema = schema_for(TABLES[name])
        namespace = name.split(".")[0]
        self.catalog.create_namespace_if_not_exists(namespace)
        try:
            table = self.catalog.load_table(name)
        except NoSuchTableError:
            return self.catalog.create_table(name, schema=schema, properties=METADATA_PROPERTIES)
        if set(schema.names) - set(table.schema().column_names):
            # Additive evolution only: schemas/ forbids renames and removals without an ADR.
            with table.update_schema() as update:
                update.union_by_name(schema)
            table = self.catalog.load_table(name)
        return table

    def append(self, name: str, records: Sequence[BaseModel]) -> None:
        if records:
            self.table(name).append(to_table(TABLES[name], records))

    def replace_source(self, name: str, parser_id: str, records: Sequence[BaseModel]) -> None:
        """Replace every row this parser wrote to ``name`` with ``records``, in one commit."""
        self._replace(name, _eq("provenance.parser_id", parser_id), records)

    def replace_all(self, name: str, records: Sequence[BaseModel]) -> None:
        """Replace the whole table, for tables rebuilt from scratch on every run."""
        self._replace(name, AlwaysTrue(), records)

    def _replace(self, name: str, rows: BooleanExpression, records: Sequence[BaseModel]) -> None:
        table = self.table(name)
        if table.current_snapshot() is None:
            self.append(name, records)
            return
        with _quiet_empty_delete():
            if records:
                table.overwrite(to_table(TABLES[name], records), overwrite_filter=rows)
            else:
                table.delete(rows)

    def read(self, name: str) -> pa.Table:
        """A model table's rows, or an empty table with its schema if it doesn't exist yet."""
        if not self.exists(name):
            return schema_for(TABLES[name]).empty_table()
        return self.table(name).scan().to_arrow()

    def write_gold(self, name: str, data: pa.Table) -> int | None:
        """Replace ``gold.<name>`` with ``data`` and return the new snapshot ID.

        Gold is rebuilt from silver every time, so it keeps no history: the old table is purged
        with its files, and a record removed by a correction can't be reached through time
        travel or left-over data files (CORRECTIONS.md).
        """
        ident = f"gold.{name}"
        self.catalog.create_namespace_if_not_exists("gold")
        if self.exists(ident):
            self.catalog.purge_table(ident)
        table = self.catalog.create_table(ident, schema=data.schema)
        table.append(data)
        snapshot = table.current_snapshot()
        return snapshot.snapshot_id if snapshot else None

    def expire_snapshots(self, older_than: datetime) -> tuple[int, int]:
        """Expire bronze, silver, and ops snapshots older than ``older_than`` (ADR 0006).

        The current snapshot is always kept. Manifest lists, manifests, and data files that no
        remaining snapshot uses are deleted after the commit, since PyIceberg only drops the
        snapshots from the metadata. Returns (snapshots expired, files deleted).
        """
        cutoff = int(older_than.timestamp() * 1000)
        expired_count = deleted = 0
        for name in TABLES:
            if not self.exists(name):
                continue
            table = self.catalog.load_table(name)
            if any(table.properties.get(k) != v for k, v in METADATA_PROPERTIES.items()):
                with table.transaction() as tx:
                    tx.set_properties(METADATA_PROPERTIES)
                table = self.catalog.load_table(name)
            current = table.current_snapshot()
            current_id = current.snapshot_id if current else None
            expired: list[Snapshot] = []
            kept: list[Snapshot] = []
            for snapshot in table.snapshots():
                old = snapshot.timestamp_ms < cutoff and snapshot.snapshot_id != current_id
                (expired if old else kept).append(snapshot)
            if not expired:
                continue
            files = _SnapshotFiles(table)
            unused = files.of(expired) - files.of(kept)
            table.maintenance.expire_snapshots().by_ids([s.snapshot_id for s in expired]).commit()
            expired_count += len(expired)
            for path in sorted(unused):
                try:
                    table.io.delete(path)
                except FileNotFoundError:
                    continue
                deleted += 1
        return expired_count, deleted

    def raw_documents(self, source_id: str) -> list[RawDocument]:
        """Every raw document fetched for a source, oldest first."""
        if not self.exists("bronze.raw_documents"):
            return []
        rows = (
            self.table("bronze.raw_documents")
            .scan(row_filter=_eq("source_id", source_id))
            .to_arrow()
            .to_pylist()
        )
        return [RawDocument.model_validate(r) for r in sorted(rows, key=lambda r: r["fetched_at"])]

    def fetched_urls(self, source_id: str) -> frozenset[str]:
        """The URL of every raw document stored for a source."""
        if not self.exists("bronze.raw_documents"):
            return frozenset()
        rows = self.table("bronze.raw_documents").scan(
            row_filter=_eq("source_id", source_id), selected_fields=("url",)
        )
        return frozenset(rows.to_arrow().column("url").to_pylist())

    def latest_raw_document(self, source_id: str) -> RawDocument | None:
        documents = self.raw_documents(source_id)
        return documents[-1] if documents else None

    def runs(self) -> list[CrawlRun]:
        return [CrawlRun.model_validate(r) for r in self.read("ops.crawl_runs").to_pylist()]

    def last_successful_run(self, kind: str, source_id: str) -> CrawlRun | None:
        if not self.exists("ops.crawl_runs"):
            return None
        rows = (
            self.table("ops.crawl_runs")
            .scan(
                row_filter=And(
                    _eq("kind", kind),
                    _eq("source_id", source_id),
                    _eq("status", "succeeded"),
                )
            )
            .to_arrow()
            .to_pylist()
        )
        if not rows:
            return None
        return CrawlRun.model_validate(max(rows, key=lambda r: r["started_at"]))
