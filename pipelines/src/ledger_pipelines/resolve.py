"""Vendor resolution: maps source vendor names to the curated vendors in ``data/seeds/``."""

import csv
import hashlib
import io
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ledger_schemas import (
    Product,
    ProductMention,
    Provenance,
    Relationship,
    UnresolvedVendorName,
    Vendor,
)

RESOLVER_ID = "vendor-resolution"
RESOLVER_VERSION = "0.1.0"  # bump when matching logic changes
SEEDS_URL = "https://github.com/csp4z/compromise-ledger/blob/main/data/seeds/vendors.csv"
SEEDS_LICENSE = "CC-BY-4.0"
SEEDS_CONFIDENCE = 90

VENDOR_COLUMNS = ["slug", "name", "is_security_vendor", "source", "note", "cpe_vendor"]
ALIAS_COLUMNS = ["alias", "vendor_slug", "note"]
CPE_VENDOR = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class SeedError(ValueError):
    """The seed files are inconsistent. The message names the file and row."""


def name_key(name: str) -> str:
    """Matching key: NFKC, case-folded, whitespace collapsed. Nothing fuzzier (Phase 2)."""
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


def product_slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:120].strip("-")
    # Names with no ASCII letters or digits still need a stable slug.
    return slug or "p-" + hashlib.sha256(name.encode()).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class SeedVendor:
    slug: str
    name: str
    is_security_vendor: bool
    source: str
    note: str
    cpe_vendor: str | None = None


@dataclass(frozen=True, slots=True)
class Seeds:
    vendors: tuple[SeedVendor, ...]
    lookup: dict[str, str]  # name_key -> vendor slug
    digest: str  # SHA-256 of both seed files, cited as the raw document

    @property
    def cpe_vendors(self) -> tuple[str, ...]:
        """The curated vendors' NVD CPE vendor names, sorted."""
        return tuple(sorted(v.cpe_vendor for v in self.vendors if v.cpe_vendor))


def _rows(path: Path, columns: list[str]) -> tuple[bytes, list[dict[str, str]]]:
    data = path.read_bytes()
    reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
    if reader.fieldnames != columns:
        raise SeedError(f"{path.name}: expected columns {columns}, got {reader.fieldnames}")
    return data, list(reader)


def load_seeds(directory: Path) -> Seeds:
    vendor_bytes, vendor_rows = _rows(directory / "vendors.csv", VENDOR_COLUMNS)
    alias_bytes, alias_rows = _rows(directory / "vendor_aliases.csv", ALIAS_COLUMNS)

    vendors: list[SeedVendor] = []
    lookup: dict[str, str] = {}
    for line, row in enumerate(vendor_rows, start=2):
        where = f"vendors.csv line {line}"
        if row["is_security_vendor"] not in ("true", "false"):
            raise SeedError(f"{where}: is_security_vendor must be true or false")
        vendor = SeedVendor(
            slug=row["slug"],
            name=row["name"],
            is_security_vendor=row["is_security_vendor"] == "true",
            source=row["source"],
            note=row["note"],
            cpe_vendor=row["cpe_vendor"] or None,
        )
        if vendor.is_security_vendor and not vendor.source.startswith("https://"):
            raise SeedError(f"{where}: a security vendor needs an https source")
        if vendor.cpe_vendor is not None:
            if not CPE_VENDOR.match(vendor.cpe_vendor):
                raise SeedError(f"{where}: cpe_vendor {vendor.cpe_vendor!r} is not a CPE vendor")
            if any(v.cpe_vendor == vendor.cpe_vendor for v in vendors):
                raise SeedError(f"{where}: cpe_vendor {vendor.cpe_vendor!r} is already used")
        if any(v.slug == vendor.slug for v in vendors):
            raise SeedError(f"{where}: duplicate slug {vendor.slug!r}")
        key = name_key(vendor.name)
        if key in lookup:
            raise SeedError(f"{where}: name {vendor.name!r} already used by {lookup[key]!r}")
        lookup[key] = vendor.slug
        vendors.append(vendor)

    slugs = {v.slug for v in vendors}
    for line, row in enumerate(alias_rows, start=2):
        where = f"vendor_aliases.csv line {line}"
        if row["vendor_slug"] not in slugs:
            raise SeedError(f"{where}: unknown vendor_slug {row['vendor_slug']!r}")
        key = name_key(row["alias"])
        if key in lookup:
            raise SeedError(f"{where}: alias {row['alias']!r} already maps to {lookup[key]!r}")
        lookup[key] = row["vendor_slug"]

    digest = hashlib.sha256(vendor_bytes + b"\0" + alias_bytes).hexdigest()
    return Seeds(vendors=tuple(vendors), lookup=lookup, digest=digest)


@dataclass(slots=True)
class Resolution:
    vendors: list[Vendor] = field(default_factory=list[Vendor])
    products: list[Product] = field(default_factory=list[Product])
    relationships: list[Relationship] = field(default_factory=list[Relationship])
    unresolved: list[UnresolvedVendorName] = field(default_factory=list[UnresolvedVendorName])


def resolve(mentions: Iterable[ProductMention], seeds: Seeds, *, built_at: datetime) -> Resolution:
    """Turn mentions into vendors, products, and ``product has vulnerability`` relationships.

    Products and relationships keep the mention's provenance (source URL, raw document,
    confidence, license) with this step as the producer, so they trace back to the source.
    """
    seed_provenance = Provenance(
        source_url=SEEDS_URL,
        raw_document_id=seeds.digest,
        crawled_at=built_at,
        parser_id=RESOLVER_ID,
        parser_version=RESOLVER_VERSION,
        confidence=SEEDS_CONFIDENCE,
        license=SEEDS_LICENSE,
    )
    vendors = {
        v.slug: Vendor(
            slug=v.slug,
            name=v.name,
            is_security_vendor=v.is_security_vendor,
            cpe_vendor=v.cpe_vendor,
            provenance=seed_provenance,
        )
        for v in seeds.vendors
    }
    products: dict[str, Product] = {}
    relationships: dict[str, Relationship] = {}
    unresolved: dict[str, tuple[str, int, set[str]]] = {}

    spellings: dict[str, Counter[str]] = defaultdict(Counter)
    # Sorted so the provenance kept for each product and relationship is stable across runs.
    ordered = sorted(
        mentions,
        key=lambda m: (m.vulnerability_id, m.vendor_name, m.product_name, m.provenance.parser_id),
    )
    for mention in ordered:
        key = name_key(mention.vendor_name)
        slug = seeds.lookup.get(key)
        if slug is None:
            name, count, parsers = unresolved.get(key, (mention.vendor_name, 0, set()))
            unresolved[key] = (name, count + 1, parsers | {mention.provenance.parser_id})
            continue
        provenance = mention.provenance.model_copy(
            update={"parser_id": RESOLVER_ID, "parser_version": RESOLVER_VERSION}
        )
        product = Product(
            vendor_id=vendors[slug].id,
            slug=product_slug(mention.product_name),
            name=mention.product_name,
            provenance=provenance,
        )
        products.setdefault(product.id, product)
        spellings[product.id][mention.product_name] += 1
        relationship = Relationship(
            relationship_type="has",
            source_ref=product.id,
            target_ref=mention.vulnerability_id,
            provenance=provenance,
        )
        relationships.setdefault(relationship.id, relationship)

    # Several spellings can share a slug ("PAN-OS", "Pan-OS"): name the product after the most
    # common one, ties broken alphabetically.
    named = [
        p.model_copy(
            update={"name": min(spellings[p.id].items(), key=lambda kv: (-kv[1], kv[0]))[0]}
        )
        for p in products.values()
    ]
    return Resolution(
        vendors=list(vendors.values()),
        products=named,
        relationships=list(relationships.values()),
        unresolved=[
            UnresolvedVendorName(vendor_name=name, mentions=count, parser_ids=sorted(parsers))
            for name, count, parsers in sorted(unresolved.values(), key=lambda t: (-t[1], t[0]))
        ],
    )
