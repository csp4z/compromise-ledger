"""Provenance carried by every silver and gold record."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ledger_schemas.types import Confidence, HttpUrlStr, Sha256Hex, UtcDatetime


class Provenance(BaseModel):
    """Where a fact came from, how it was extracted, and how much it is trusted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_url: HttpUrlStr | None = Field(
        default=None, description="Public URL of the source document."
    )
    source_url_sha256: Sha256Hex | None = Field(
        default=None,
        description="SHA-256 of the source URL, used instead of source_url for leak-site posts.",
    )
    raw_document_id: Sha256Hex = Field(description="ID of the bronze raw document parsed.")
    crawled_at: UtcDatetime
    parser_id: str = Field(min_length=1, max_length=128)
    parser_version: str = Field(min_length=1, max_length=64)
    confidence: Confidence
    license: str = Field(
        min_length=1, max_length=128, description="Upstream license (SPDX ID or LicenseRef-*)."
    )

    @model_validator(mode="after")
    def _exactly_one_source(self) -> Self:
        if (self.source_url is None) == (self.source_url_sha256 is None):
            raise ValueError("set exactly one of source_url or source_url_sha256")
        return self
