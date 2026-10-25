"""Rows of ``ops.crawl_runs``: one per crawl or parse run, read by health checks."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ledger_schemas.types import Slug, UtcDatetime

RunKind = Literal["crawl", "parse"]
RunStatus = Literal["succeeded", "failed"]


class CrawlRun(BaseModel):
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
