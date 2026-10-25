"""Rows of ``bronze.raw_documents``: the contract between crawler and parser plugins."""

from pydantic import BaseModel, ConfigDict, Field

from ledger_schemas.types import HttpUrlStr, Sha256Hex, Slug, UtcDatetime


class RawDocument(BaseModel):
    """One fetched document. The body is stored as a content-addressed blob, not in the row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Sha256Hex = Field(description="SHA-256 of the body; also the blob's address.")
    source_id: Slug = Field(description="ID of the crawler that fetched it.")
    crawler_version: str = Field(min_length=1, max_length=64)
    url: HttpUrlStr
    fetched_at: UtcDatetime
    http_status: int = Field(ge=100, le=599)
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0)

    @property
    def blob_key(self) -> str:
        """Object-storage key of the body: ``raw/{source_id}/{sha256[:2]}/{sha256}``."""
        return f"raw/{self.source_id}/{self.id[:2]}/{self.id}"
