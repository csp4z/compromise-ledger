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
    AttackType,
    BreachCause,
    CpeVendor,
    CveCountScope,
    CveId,
    CvssScorer,
    CvssSeverity,
    CweId,
    IncidentStatus,
    Jurisdiction,
    Probability,
    RansomwareUse,
    RelationshipType,
    SecAccession,
    SecCik,
    SecForm,
    SecItem,
    Slug,
    SsvcAutomatable,
    SsvcExploitation,
    SsvcTechnicalImpact,
    StixId,
    UtcDatetime,
)


class Vendor(DomainObject):
    """A product vendor. STIX ``identity`` with ``identity_class: organization``."""

    stix_type = "identity"

    slug: Slug
    name: str = Field(min_length=1, max_length=256)
    is_security_vendor: bool = Field(description="On the curated security-vendor list.")
    cpe_vendor: CpeVendor | None = Field(
        default=None, description="The vendor's name in NVD's CPE dictionary, where curated."
    )
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
    cvss_v3_scorer: CvssScorer | None = Field(
        default=None, description="Who produced this row's CVSS score."
    )
    cwe_ids: list[CweId] = Field(default_factory=list[CweId])
    kev_date_added: date | None = None
    kev_due_date: date | None = None
    kev_ransomware_use: RansomwareUse | None = None
    cve_assigner: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Short name of the CNA that assigned the CVE ID, as the CVE List writes it.",
    )
    cve_reserved: UtcDatetime | None = Field(
        default=None, description="When the CVE ID was reserved, before publication."
    )
    ssvc_exploitation: SsvcExploitation | None = None
    ssvc_automatable: SsvcAutomatable | None = None
    ssvc_technical_impact: SsvcTechnicalImpact | None = None
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


class CveCount(DomainObject):
    """NVD's count of CVEs whose CPE configurations name a vendor.

    Keyed by the CPE vendor name rather than a ``Vendor`` ID: parsers don't resolve entities,
    and gold joins the count to the vendor through ``Vendor.cpe_vendor``. The count's date is
    ``provenance.crawled_at``.
    """

    stix_type = "x-ledger-cve-count"

    cpe_vendor: CpeVendor
    scope: CveCountScope
    cve_count: int = Field(ge=0)
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        return (self.cpe_vendor, self.scope)


class Organization(DomainObject):
    """An organization that disclosed or suffered an incident. STIX ``identity`` with
    ``identity_class: organization``.

    Keyed by SEC CIK, the only source of organizations so far. Organizations from sources without
    a CIK will get another identifier as an additive change, and entity resolution (Phase 2)
    merges records for the same organization.
    """

    stix_type = "identity"

    sec_cik: SecCik
    name: str = Field(min_length=1, max_length=256)
    tickers: list[str] = Field(default_factory=list[str])
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        return ("sec-cik", self.sec_cik)


class Incident(DomainObject):
    """A security incident as disclosed in one SEC filing. STIX ``incident``; the fields below go
    in a project extension when exported.

    An 8-K/A amending an earlier disclosure is its own record (``sec_form`` "8-K/A"), so counts
    of incidents use original filings only.
    """

    stix_type = "incident"

    organization_id: StixId
    status: IncidentStatus
    disclosed_on: date = Field(description="Filing date.")
    sec_accession: SecAccession
    sec_form: SecForm
    sec_item: SecItem = Field(description="The 8-K item that carries the disclosure.")
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        return ("sec", self.sec_accession)

    @model_validator(mode="after")
    def _organization_is_identity(self) -> Self:
        if id_type(self.organization_id) != Organization.stix_type:
            raise ValueError("organization_id must be an identity ID")
        return self


class ThirdPartyIncident(DomainObject):
    """A curated mark: the incident an SEC filing discloses happened at a third party, such as a
    vendor or service provider holding the company's or its customers' data, not in systems the
    company runs (its own cloud accounts included).

    Kept by hand in ``data/seeds/third_party_incidents.csv`` after reading the filing, and joined
    to incidents by accession number in gold.
    """

    stix_type = "x-ledger-third-party-incident"

    sec_accession: SecAccession
    third_party: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="The third party's name, only when the filing itself names it.",
    )
    note: str = Field(min_length=1, max_length=500, description="What the filing says, briefly.")
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        return ("sec", self.sec_accession)


class EpssScore(DomainObject):
    """A CVE's EPSS score on one day: FIRST's estimate of the probability that it is exploited
    in the following 30 days, and where that ranks among all scored CVEs.

    One row per CVE and day asked for. A CVE that had no score on that day has no row.
    """

    stix_type = "x-ledger-epss-score"

    vulnerability_id: StixId
    cve_id: CveId
    score_date: date
    epss: Probability
    percentile: Probability
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        return (self.cve_id, self.score_date.isoformat())

    @model_validator(mode="after")
    def _refs_vulnerability(self) -> Self:
        if id_type(self.vulnerability_id) != Vulnerability.stix_type:
            raise ValueError("vulnerability_id must be a vulnerability ID")
        return self


class BreachNotice(DomainObject):
    """A data-breach notification an organization filed with a state attorney general.
    STIX ``incident``; the fields below go in a project extension when exported.

    The notifier is the organization that owns the data, which is not always the one that was
    breached. It is kept by the name on the notice, and becomes an ``Organization`` when entity
    resolution can match notices to each other and to SEC filers (Phase 2). The name is left
    out when the notifier looks like one person's professional practice. Dates are the
    organization's own account: when the breach began and ended, when it became aware, and when
    the notice reached the attorney general. Nothing about the people affected is kept beyond
    their number.
    """

    stix_type = "incident"

    jurisdiction: Jurisdiction
    notice_id: str = Field(
        min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$", description="The regulator's ID."
    )
    organization_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="The notifier's name; withheld for what looks like an individual's practice.",
    )
    status: IncidentStatus
    submitted_on: date = Field(description="When the notice reached the attorney general.")
    aware_on: date | None = Field(default=None, description="When the organization became aware.")
    breach_started_on: date | None = None
    breach_ended_on: date | None = None
    cause: BreachCause | None = None
    attack_type: AttackType | None = Field(
        default=None, description="For cyberattacks, the kind the notice reports."
    )
    industry: str | None = Field(
        default=None, min_length=1, max_length=64, description="The regulator's industry label."
    )
    organization_state: str | None = Field(
        default=None, pattern=r"^[A-Z]{2}$", description="Where the organization is based."
    )
    residents_affected: int | None = Field(
        default=None, ge=0, description="Residents of the jurisdiction whose data was involved."
    )
    provenance: Provenance

    def natural_key(self) -> tuple[str, ...]:
        return ("breach-notice", self.jurisdiction.lower(), self.notice_id)
