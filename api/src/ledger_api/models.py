"""Response models: the gold export columns, documented for OpenAPI."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    total: int = Field(description="Rows matching the filters, across all pages.")
    limit: int
    offset: int
    items: list[T]


class KevEntry(BaseModel):
    """One KEV entry and one affected vendor product (gold.kev_vendor_products)."""

    cve_id: str
    vendor_slug: str
    vendor_name: str
    is_security_vendor: bool
    product_name: str
    kev_date_added: date
    kev_due_date: date | None
    kev_ransomware_use: Literal["known", "unknown"] | None
    published: datetime | None = Field(description="NVD publication time (UTC).")
    days_to_kev: int | None = Field(description="Days from publication to KEV listing.")
    source_url: str
    crawled_at: datetime
    confidence: int
    license: str


class Vulnerability(BaseModel):
    """One CVE, merged across sources (gold.vulnerabilities)."""

    cve_id: str
    description: str | None
    published: datetime | None
    last_modified: datetime | None
    cvss_v3_base_score: float | None
    cvss_v3_severity: str | None
    cwe_ids: str | None = Field(description="';'-separated CWE IDs.")
    in_kev: bool
    kev_date_added: date | None
    kev_due_date: date | None
    kev_ransomware_use: Literal["known", "unknown"] | None
    days_to_kev: int | None
    sources: str = Field(description="';'-separated source IDs.")
    source_urls: str
    crawled_at: datetime
    confidence: int
    licenses: str


class VulnerabilityDetail(Vulnerability):
    products: list[KevEntry] = Field(description="Affected vendor products named by KEV.")


class Vendor(BaseModel):
    """A curated vendor and its KEV totals (gold.vendors)."""

    slug: str
    name: str
    is_security_vendor: bool
    kev_count: int
    kev_ransomware_known: int
    kev_products: int
    first_kev_date: date | None
    last_kev_date: date | None


class VendorDetail(Vendor):
    kev: list[KevEntry]


class GroupSummary(BaseModel):
    """Security vendors vs everyone else (gold.security_vendor_summary)."""

    vendor_group: Literal["security_vendors", "all_other_vendors"]
    kev_count: int
    ransomware_known: int
    ransomware_share: float
    recent_cves: int = Field(description="CVEs published since the KEV launch date.")
    median_days_to_kev: float | None
    p25_days_to_kev: float | None
    p75_days_to_kev: float | None
    share_within_7_days: float | None
    time_to_kev_published_since: date


class Month(BaseModel):
    """KEV additions in one month (gold.security_vendor_kev_monthly)."""

    month: date
    kev_added: int
    security_vendor_kev_added: int
    security_vendor_share: float


class UnresolvedVendorName(BaseModel):
    vendor_name: str
    mentions: int
    sources: str


class Health(BaseModel):
    status: Literal["ok"]
    generated_at: datetime
    schema_version: str
