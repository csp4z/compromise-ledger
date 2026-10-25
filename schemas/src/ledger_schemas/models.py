"""STIX-aligned silver models (ADR 0004).

Natural keys, which determine each ID, are listed in ``schemas/README.md``.
"""

import hashlib
from datetime import date
from typing import Self

from pydantic import Field, model_validator

from ledger_schemas.base import DomainObject
from ledger_schemas.ids import id_type
from ledger_schemas.provenance import Provenance
from ledger_schemas.types import (
    CveId,
    CvssSeverity,
    CweId,
    RansomwareUse,
    RelationshipType,
    Slug,
    StixId,
    UtcDatetime,
)


class Vendor(DomainObject):
    """A product vendor. STIX ``identity`` with ``identity_class: organization``."""

    stix_type = "identity"

    slug: Slug
    name: str = Field(min_length=1, max_length=256)
    is_security_vendor: bool = Field(description="On the curated security-vendor list.")
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        return (self.slug,)


class Product(DomainObject):
    """A vendor's product. STIX ``software``."""

    stix_type = "software"

    vendor_id: StixId
    slug: Slug
    name: str = Field(min_length=1, max_length=256)
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        return (self.vendor_id, self.slug)

    @model_validator(mode="after")
    def _vendor_is_identity(self) -> Self:
        if id_type(self.vendor_id) != Vendor.stix_type:
            raise ValueError("vendor_id must be an identity ID")
        return self


class Vulnerability(DomainObject):
    """A CVE. STIX ``vulnerability``; KEV fields go in a project extension when exported.

    Each source fills the fields it knows and leaves the rest null. Silver keeps one row per
    vulnerability per source, and gold merges them.
    """

    stix_type = "vulnerability"

    cve_id: CveId
    description: str | None = None
    published: UtcDatetime | None = None
    last_modified: UtcDatetime | None = None
    cvss_v3_base_score: float | None = Field(default=None, ge=0, le=10)
    cvss_v3_severity: CvssSeverity | None = None
    cwe_ids: list[CweId] = Field(default_factory=list[CweId])
    kev_date_added: date | None = None
    kev_due_date: date | None = None
    kev_ransomware_use: RansomwareUse | None = None
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        return (self.cve_id,)


class Relationship(DomainObject):
    """A typed link between two objects. STIX ``relationship``; confidence is in provenance."""

    stix_type = "relationship"

    relationship_type: RelationshipType
    source_ref: StixId
    target_ref: StixId
    start_time: UtcDatetime | None = None
    stop_time: UtcDatetime | None = None
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        return (self.relationship_type, self.source_ref, self.target_ref)

    @model_validator(mode="after")
    def _time_order(self) -> Self:
        if self.start_time and self.stop_time and self.stop_time < self.start_time:
            raise ValueError("stop_time must not be before start_time")
        return self


class ProductMention(DomainObject):
    """A vendor and product named by a source, before entity resolution.

    Names are kept as the source gives them (whitespace normalized only). Resolution maps them
    through the vendor alias table to ``Vendor`` and ``Product`` records and a ``has``
    relationship; names that don't resolve are published as the unresolved list.
    """

    stix_type = "x-ledger-product-mention"

    vulnerability_id: StixId
    vendor_name: str = Field(min_length=1, max_length=256)
    product_name: str = Field(min_length=1, max_length=256)
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        # Free-text names may contain the key separator, so they enter the key as a digest.
        names = hashlib.sha256(f"{self.vendor_name}\0{self.product_name}".encode()).hexdigest()
        return (self.vulnerability_id, names)

    @model_validator(mode="after")
    def _refs_vulnerability(self) -> Self:
        if id_type(self.vulnerability_id) != Vulnerability.stix_type:
            raise ValueError("vulnerability_id must be a vulnerability ID")
        return self
