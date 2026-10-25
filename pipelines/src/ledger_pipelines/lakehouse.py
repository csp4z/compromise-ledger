"""Iceberg tables through PyIceberg's SQL catalog (ADR 0003)."""

import warnings
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import pyarrow as pa
from ledger_schemas import (
    Correction,
    CrawlRun,
    Product,
    ProductMention,
    RawDocument,
    Relationship,
    UnresolvedVendorName,
    Vendor,
    Vulnerability,
)
from pydantic import BaseModel
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.expressions import AlwaysTrue, And, BooleanExpression, EqualTo
from pyiceberg.table import Table

from ledger_pipelines.arrow import schema_for, to_table
from ledger_pipelines.config import Settings

TABLES: dict[str, type[BaseModel]] = {
    "bronze.raw_documents": RawDocument,
    "silver.vendors": Vendor,
    "silver.products": Product,
    "silver.vulnerabilities": Vulnerability,
    "silver.relationships": Relationship,
    "silver.product_mentions": ProductMention,
    "silver.corrections": Correction,
    "ops.crawl_runs": CrawlRun,
    "ops.unresolved_vendor_names": UnresolvedVendorName,
}

# Where parser output goes. Corrections are maintainer decisions, never parser output.
PARSER_TABLES: dict[type[BaseModel], str] = {
    model: name
    for name, model in TABLES.items()
    if name.startswith("silver.") and model is not Correction
}


@contextmanager
def _quiet_empty_delete() -> Iterator[None]:
    """Silence PyIceberg's warning when an overwrite or delete finds nothing to remove.

    That is expected on a source's first write to a shared table, or when a table was empty.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "Delete operation did not match any records")
        yield


def _shape(schema: pa.Schema) -> list[tuple[str, str]]:
    # Iceberg reads strings back as large_string; treat the two as the same type.
    return [(f.name, str(f.type).replace("large_string", "string")) for f in schema]


def _eq(column: str, value: str) -> BooleanExpression:
    # PyIceberg's predicates are Pydantic models whose __init__ pyright can't see.
    return EqualTo(column, value)  # pyright: ignore[reportCallIssue]


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
            return self.catalog.create_table(name, schema=schema)
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

        Gold is rebuilt from silver every time, so a changed shape recreates the table.
        """
        ident = f"gold.{name}"
        self.catalog.create_namespace_if_not_exists("gold")
        if self.exists(ident):
            table = self.catalog.load_table(ident)
            if _shape(table.schema().as_arrow()) != _shape(data.schema):
                self.catalog.purge_table(ident)
        if not self.exists(ident):
            table = self.catalog.create_table(ident, schema=data.schema)
        table = self.catalog.load_table(ident)
        if table.current_snapshot() is None:
            table.append(data)
        else:
            with _quiet_empty_delete():
                table.overwrite(data)
        snapshot = table.current_snapshot()
        return snapshot.snapshot_id if snapshot else None

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
