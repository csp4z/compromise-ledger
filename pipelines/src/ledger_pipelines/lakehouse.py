"""Iceberg tables through PyIceberg's SQL catalog (ADR 0003)."""

import warnings
from collections.abc import Sequence

from ledger_schemas import (
    Correction,
    CrawlRun,
    Product,
    ProductMention,
    RawDocument,
    Relationship,
    Vendor,
    Vulnerability,
)
from pydantic import BaseModel
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.expressions import And, BooleanExpression, EqualTo
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
}

# Where parser output goes. Corrections are maintainer decisions, never parser output.
PARSER_TABLES: dict[type[BaseModel], str] = {
    model: name
    for name, model in TABLES.items()
    if name.startswith("silver.") and model is not Correction
}


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
        table = self.table(name)
        rows = _eq("provenance.parser_id", parser_id)
        if table.current_snapshot() is None:
            self.append(name, records)
            return
        with warnings.catch_warnings():
            # Expected on this parser's first write to a table other sources already use.
            warnings.filterwarnings("ignore", "Delete operation did not match any records")
            if records:
                table.overwrite(to_table(TABLES[name], records), overwrite_filter=rows)
            else:
                table.delete(rows)

    def latest_raw_document(self, source_id: str) -> RawDocument | None:
        if not self.exists("bronze.raw_documents"):
            return None
        rows = (
            self.table("bronze.raw_documents")
            .scan(row_filter=_eq("source_id", source_id))
            .to_arrow()
            .to_pylist()
        )
        if not rows:
            return None
        return RawDocument.model_validate(max(rows, key=lambda r: r["fetched_at"]))

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
