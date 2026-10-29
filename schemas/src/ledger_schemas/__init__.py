"""STIX-aligned data contracts shared by all Compromise Ledger components."""

from importlib.metadata import version

from ledger_schemas.corrections import Correction
from ledger_schemas.ids import PROJECT_NAMESPACE, make_id
from ledger_schemas.models import (
    CveCount,
    Incident,
    Organization,
    Product,
    ProductMention,
    Relationship,
    Vendor,
    Vulnerability,
)
from ledger_schemas.ops import CrawlRun, UnresolvedVendorName
from ledger_schemas.provenance import Provenance
from ledger_schemas.raw import RawDocument

__version__ = version("ledger-schemas")

# Version of the data contract, recorded in exports and manifests. Bump the minor version for
# additive changes; anything else needs an ADR.
SCHEMA_VERSION = "0.7.0"

__all__ = [
    "PROJECT_NAMESPACE",
    "SCHEMA_VERSION",
    "Correction",
    "CrawlRun",
    "CveCount",
    "Incident",
    "Organization",
    "Product",
    "ProductMention",
    "Provenance",
    "RawDocument",
    "Relationship",
    "UnresolvedVendorName",
    "Vendor",
    "Vulnerability",
    "make_id",
]
