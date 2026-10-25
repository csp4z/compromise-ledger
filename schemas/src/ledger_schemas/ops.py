"""Operational tables: run history and the published list of unresolved names."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ledger_schemas.types import Slug, UtcDatetime

RunKind = Literal["crawl", "parse", "resolve", "build", "export"]
RunStatus = Literal["succeeded", "failed"]


class CrawlRun(BaseModel):
    """A row of ``ops.crawl_runs``: one per pipeline step run (crawl, parse, resolve, ...)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(description="'<kind>:<source_id>:<started_at, compact UTC>'.")
    kind: RunKind
    source_id: Slug
    plugin_version: str = Field(min_length=1, max_length=64)
    started_at: UtcDatetime
    finished_at: UtcDatetime
    status: RunStatus
    documents: int = Field(ge=0, description="Documents fetched (crawl) or parsed (parse).")
    records: int = Field(ge=0, description="Silver records written (parse only).")
    error: str | None = Field(default=None, max_length=2000)


class UnresolvedVendorName(BaseModel):
    """A row of ``ops.unresolved_vendor_names``: a source's vendor name with no seed match.

    Published so readers can see what the vendor counts leave out, and so aliases get added.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    vendor_name: str = Field(min_length=1, max_length=256)
    mentions: int = Field(ge=1)
    parser_ids: list[Slug] = Field(min_length=1)
