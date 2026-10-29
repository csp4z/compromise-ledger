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


class VendorCveCount(BaseModel):
    """NVD's CVE count for a curated vendor and how many reached KEV (gold.vendor_cve_counts).

    Both counts match the vendor's CPE name in NVD, so they compare with each other. They follow
    how the vendor assigns CVEs and how far NVD has assigned CPEs, and for platform vendors
    (Microsoft, Apple, Google, Linux) they include CVEs in products that run on the platform.
    """

    slug: str
    name: str
    is_security_vendor: bool
    cpe_vendor: str = Field(description="The vendor's name in NVD's CPE dictionary.")
    nvd_cve_count: int = Field(description="CVEs whose NVD CPE configurations name the vendor.")
    nvd_kev_count: int = Field(description="Those of them in CISA KEV.")
    kev_share: float | None = Field(description="nvd_kev_count / nvd_cve_count.")
    counted_at: datetime


class Incident(BaseModel):
    """A cybersecurity incident a company disclosed in SEC 8-K filings (gold.incidents).

    A company's filings about one incident are grouped: an Item 8.01 report followed by an Item
    1.05 filing, and amendments. Disclosure under 8.01 is found by text match, so 8.01-only
    incidents are a lower bound and carry lower confidence.
    """

    incident_id: str = Field(description="The ID of the incident's first filing.")
    organization_id: str
    organization_name: str = Field(description="The company's name as EDGAR records it.")
    sec_cik: str
    tickers: str | None = Field(description="';'-separated ticker symbols.")
    status: Literal["claimed", "reported", "confirmed"]
    first_disclosed_on: date
    last_filed_on: date
    filings: int
    material: bool = Field(description="Filed under Item 1.05: the company judged it material.")
    confidence: int
    source_url: str = Field(description="The first filing on EDGAR.")
    sec_accessions: str = Field(description="';'-separated accession numbers, oldest first.")


class UnresolvedVendorName(BaseModel):
    vendor_name: str
    mentions: int
    sources: str


class Health(BaseModel):
    status: Literal["ok"]
    generated_at: datetime
    schema_version: str
