"""Rows of ``silver.corrections`` (see CORRECTIONS.md)."""

from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from ledger_schemas.base import DomainObject
from ledger_schemas.types import CorrectionAction, CorrectionReason, StixId, UtcDatetime

RequestRef = Annotated[str, StringConstraints(pattern=r"^(github|private)#[A-Za-z0-9-]+$")]


class Correction(DomainObject):
    """An accepted correction request, applied before any gold build, API response, or export.

    Corrections are maintainer decisions, not parsed source data, so they carry an audit trail
    (``request_ref``, ``decided_at``) instead of ``Provenance``. ``public_note`` appears in the
    public changelog and must not repeat removed content.
    """

    stix_type = "x-ledger-correction"

    request_ref: RequestRef = Field(description="'github#<issue>' or 'private#<case>'.")
    target_id: StixId
    action: CorrectionAction
    amend_field: str | None = Field(default=None, min_length=1, max_length=128)
    amend_value: str | None = Field(default=None, description="New value, JSON-encoded.")
    reason: CorrectionReason
    decided_at: UtcDatetime
    public_note: str | None = Field(default=None, max_length=1000)

    def natural_key(self) -> tuple[str, ...]:
        key = (self.request_ref, self.target_id)
        return (*key, self.amend_field) if self.amend_field else key

    @model_validator(mode="after")
    def _amend_fields(self) -> Self:
        amending = self.action == "amend"
        if amending != (self.amend_field is not None) or amending != (self.amend_value is not None):
            raise ValueError("amend_field and amend_value are required for amend, and only for it")
        return self
