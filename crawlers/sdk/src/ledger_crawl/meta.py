"""Plugin metadata: what a crawler or parser declares about itself."""

from typing import Literal

from ledger_schemas.types import Confidence, Slug
from pydantic import BaseModel, ConfigDict, Field

Network = Literal["clearnet", "tor"]
ParseMode = Literal["snapshot", "incremental"]


class RateLimit(BaseModel):
    """At most ``requests`` per ``per_seconds``, spread evenly."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requests: int = Field(ge=1)
    per_seconds: float = Field(gt=0)

    @property
    def interval(self) -> float:
        return self.per_seconds / self.requests


class CrawlerMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Slug = Field(description="Source ID; also the raw-document source_id.")
    version: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=500)
    network: Network = "clearnet"
    schedule: str = Field(
        pattern=r"^\S+ \S+ \S+ \S+ \S+$", description="Cron expression (UTC), five fields."
    )
    rate_limit: RateLimit
    license: str = Field(min_length=1, max_length=128, description="Upstream license (SPDX).")
    allowed_hosts: tuple[str, ...] = Field(
        min_length=1, description="Exact hostnames the crawler may request, redirects included."
    )
    content_types: tuple[str, ...] = Field(
        min_length=1, description="Accepted media types, without parameters."
    )
    max_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    max_age_hours: int = Field(
        default=36, ge=1, description="Health checks fail when the last good crawl is older."
    )
    retries: int = Field(
        default=0,
        ge=0,
        le=5,
        description=(
            "Extra attempts for a failed request (dropped connection, timeout, 429, 5xx), "
            "with exponential backoff. For sources known to be flaky."
        ),
    )
    attribution: str | None = Field(
        default=None, max_length=500, description="Notice the upstream terms require on reuse."
    )


class ParserMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Slug
    version: str = Field(min_length=1, max_length=64)
    source_id: Slug = Field(description="The crawler whose raw documents this parser reads.")
    confidence: Confidence = Field(description="Default confidence for facts from this source.")
    mode: ParseMode = Field(
        default="snapshot",
        description=(
            "snapshot: each document is the whole source; the latest replaces all rows. "
            "incremental: documents carry changes; rows are rebuilt from every document, "
            "newest record per ID winning."
        ),
    )
