"""Plugin metadata: what a crawler or parser declares about itself."""

from typing import Literal

from ledger_schemas.types import Confidence, Slug
from pydantic import BaseModel, ConfigDict, Field

Network = Literal["clearnet", "tor"]


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


class ParserMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Slug
    version: str = Field(min_length=1, max_length=64)
    source_id: Slug = Field(description="The crawler whose raw documents this parser reads.")
    confidence: Confidence = Field(description="Default confidence for facts from this source.")
