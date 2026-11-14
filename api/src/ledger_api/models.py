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
    published: datetime | None = Field(
        description="CVE publication time (UTC): the earlier of the CVE List's and NVD's."
    )
    days_to_kev: int | None = Field(description="Days from publication to KEV listing.")
    source_url: str
    crawled_at: datetime
    confidence: int
    license: str


class Vulnerability(BaseModel):
    """One CVE, merged across sources (gold.vulnerabilities)."""

    cve_id: str
    description: str | None
    published: datetime | None = Field(
        description="CVE publication time (UTC): the earlier of the CVE List's and NVD's."
    )
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
    cve_assigner: str | None = Field(description="The CNA that assigned the CVE ID.")
    cve_reserved: datetime | None = Field(description="When the CVE ID was reserved.")
    days_reserved_before_published: int | None
    nvd_cvss_v3_base_score: float | None = Field(description="NVD analysts' own score.")
    cna_cvss_v3_base_score: float | None = Field(description="The assigning CNA's own score.")
    ssvc_exploitation: Literal["none", "poc", "active"] | None
    ssvc_automatable: Literal["no", "yes"] | None = Field(
        description="CISA's SSVC: can exploitation be automated?"
    )
    ssvc_technical_impact: Literal["partial", "total"] | None = Field(
        description="CISA's SSVC: partial or total control of the product."
    )
    epss_before_kev: float | None = Field(
        description="EPSS score on the day before the KEV listing; null if it had none that day."
    )
    epss_percentile_before_kev: float | None
    epss_score_date: date | None


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
    via_third_party: bool = Field(
        default=False,
        description="The incident happened at a vendor or service provider, not in systems the "
        "company runs (a curated list, checked against each filing).",
    )
    third_party: str | None = Field(
        default=None, description="The vendor, only when the company's filing names it."
    )


class Signals(BaseModel):
    """What SSVC, CVSS, and EPSS say about a set of KEV entries. Counts, with the number each
    one was measured over, because the sets are small."""

    kev_count: int
    ssvc_assessed: int = Field(description="Entries with CISA SSVC decision points.")
    automatable: int = Field(description="SSVC says exploitation can be automated.")
    total_impact: int = Field(description="SSVC says exploitation gives total control.")
    automatable_total: int = Field(description="Both: the flaws that suit mass exploitation.")
    cvss_both_scored: int = Field(description="Scored by both NVD and the assigning CNA.")
    cna_scored_lower: int = Field(description="The CNA's base score is below NVD's.")
    cna_scored_higher: int
    epss_asked: int = Field(description="Entries whose pre-listing EPSS score was looked up.")
    epss_scored: int = Field(description="Had an EPSS score on the day before the KEV listing.")
    epss_unscored: int = Field(description="Had none: mostly CVEs that were not public yet.")
    epss_under_10pct: int = Field(description="Scored below 0.1 the day before listing.")
    median_epss_before_kev: float | None
    median_days_reserved_before_published: float | None = Field(
        description="Median days a CVE ID was reserved before the CVE was published."
    )


class VendorSignals(Signals):
    """One vendor's KEV entries (gold.vendor_signals)."""

    slug: str
    name: str
    is_security_vendor: bool


class GroupSignals(Signals):
    """Security vendors vs everyone else (gold.security_vendor_signals)."""

    vendor_group: Literal["security_vendors", "all_other_vendors"]
    automatable_total_share: float | None = Field(description="Of ssvc_assessed.")
    cna_scored_lower_share: float | None = Field(description="Of cvss_both_scored.")
    epss_unscored_share: float | None = Field(description="Of epss_asked.")
    epss_under_10pct_share: float | None = Field(description="Of epss_scored.")


class BreachNoticeStats(BaseModel):
    """Breach notifications filed with the Washington Attorney General, aggregated. Day counts
    use the dates each organization reported, and skip notices whose dates are missing or out
    of order. No endpoint names the notifying organizations."""

    notices: int
    ransomware: int
    ransomware_share: float
    discover_measured: int = Field(description="Notices with usable start and awareness dates.")
    median_days_to_discover: float | None = Field(
        description="Median days from the breach starting to the organization becoming aware."
    )
    notify_measured: int
    median_days_to_notify: float | None = Field(
        description="Median days from becoming aware to notifying the Attorney General."
    )
    share_notified_after_30_days: float | None = Field(description="Of notify_measured.")
    residents_affected: int | None = Field(description="Washington residents, summed.")
    latest_notice_on: date


class BreachNoticeYear(BreachNoticeStats):
    """One calendar year of filing (gold.breach_notice_yearly). The latest year is partial."""

    year: int
    cyberattacks: int


class BreachNoticeGroup(BreachNoticeStats):
    """All years, for one value of one dimension (gold.breach_notice_groups)."""

    dimension: Literal["industry", "cause", "attack_type"]
    label: str
    first_notice_on: date


class UnresolvedVendorName(BaseModel):
    vendor_name: str
    mentions: int
    sources: str


class Health(BaseModel):
    status: Literal["ok"]
    generated_at: datetime
    schema_version: str
