"""Base class for domain objects with deterministic IDs."""

from typing import Any, ClassVar, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ledger_schemas.ids import make_id
from ledger_schemas.types import StixId


def _no_default(schema: dict[str, Any]) -> None:
    schema.pop("default", None)


def _id_required(schema: dict[str, Any]) -> None:
    # Stored rows always have an ID, so the published JSON Schema requires it.
    required = cast(list[str], schema.setdefault("required", []))
    if "id" not in required:
        required.insert(0, "id")


class DomainObject(BaseModel):
    """A record whose ``id`` is derived from its natural key with :func:`make_id`.

    Leave ``id`` out to have it derived. If it is supplied (for example when reading a row back),
    it must match the derived value, so a record can never carry a random or stale ID.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", json_schema_extra=_id_required)

    stix_type: ClassVar[str]

    # The default only lets type checkers accept constructors without `id`: `_derive_id` always
    # replaces it, and an empty string would fail `StixId` anyway.
    id: StixId = Field(
        default="",
        description="Derived from the natural key with make_id().",
        json_schema_extra=_no_default,
    )

    def natural_key(self) -> tuple[str, ...]:
        raise NotImplementedError

    @model_validator(mode="before")
    @classmethod
    def _derive_id(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        fields = cast(dict[str, Any], data)
        if "id" in fields:
            return fields
        try:
            key = cls.model_construct(**fields).natural_key()
            derived = make_id(cls.stix_type, *key)
        except (AttributeError, TypeError, ValueError):
            # Missing or malformed key fields: let field validation report them.
            return fields
        return {**fields, "id": derived}

    @model_validator(mode="after")
    def _check_id(self) -> Self:
        expected = make_id(self.stix_type, *self.natural_key())
        if self.id != expected:
            raise ValueError(f"id {self.id!r} does not match natural key (expected {expected!r})")
        return self
