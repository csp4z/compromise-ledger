"""Constrained field types and vocabularies shared across models."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, Field, StringConstraints

from ledger_schemas.ids import ID_PATTERN


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]
"""Timezone-aware datetime, normalized to UTC. Naive datetimes are rejected."""

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=128)]
"""Lower-case, hyphen-separated canonical name. Part of natural keys, so it must never change."""

StixId = Annotated[str, StringConstraints(pattern=ID_PATTERN)]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
HttpUrlStr = Annotated[str, StringConstraints(pattern=r"^https?://\S+$", max_length=2048)]
CveId = Annotated[str, StringConstraints(pattern=r"^CVE-\d{4}-\d{4,}$")]
CweId = Annotated[str, StringConstraints(pattern=r"^(CWE-\d+|NVD-CWE-Other|NVD-CWE-noinfo)$")]
Confidence = Annotated[int, Field(ge=0, le=100)]
"""STIX confidence scale."""
CpeVendor = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=128)]
"""The vendor part of a CPE 2.3 name, as NVD writes it (``paloaltonetworks``)."""


# STIX 2.1 relationship types used so far. Extend additively.
RelationshipType = Literal["has"]

CvssSeverity = Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

# CISA KEV `knownRansomwareCampaignUse`. "unknown" is not "no", so this stays a vocabulary.
RansomwareUse = Literal["known", "unknown"]

# What a CVE count covers: every CVE NVD matches to the vendor, or only those in KEV.
CveCountScope = Literal["all", "kev"]

CorrectionAction = Literal["suppress", "amend"]
CorrectionReason = Literal[
    "inaccurate", "outdated", "misattributed", "disputed", "retracted", "out-of-policy"
]
