-- One row per vendor with KEV entries: what three independent signals say about its exploited
-- flaws. Counts, not shares, because most vendors have few entries. A CVE that affects several
-- of a vendor's products counts once.
--   SSVC (CISA, in the CVE record): could exploitation be automated, and does it give total
--     control of the product? "automatable_total" is both: the flaws that suit mass exploitation.
--   CVSS: the assigning CNA's own base score against NVD's analysts', where both scored it.
--     The CNA is usually the vendor or a programme acting for it, but not always.
--   EPSS: the exploit-prediction score on the day before the KEV listing. "epss_unscored" had
--     no score that day (mostly CVEs that were not public yet); "epss_under_10pct" were scored
--     below a 10% chance of exploitation in the next 30 days.
WITH by_cve AS (
    SELECT DISTINCT
        k.vendor_id,
        k.vendor_slug,
        k.vendor_name,
        k.is_security_vendor,
        v.*
    FROM gold.kev_vendor_products AS k
    JOIN gold.vulnerabilities AS v ON v.id = k.vulnerability_id
),
epss_through AS (
    -- Listings later than this have not been asked about yet, so they are left out of the EPSS
    -- counts instead of being counted as unscored.
    SELECT max(score_date) + 1 AS listed_through FROM silver.epss_scores
)
SELECT
    vendor_id,
    vendor_slug AS slug,
    vendor_name AS name,
    is_security_vendor,
    count(*) AS kev_count,
    count(ssvc_automatable) AS ssvc_assessed,
    count(*) FILTER (WHERE ssvc_automatable = 'yes') AS automatable,
    count(*) FILTER (WHERE ssvc_technical_impact = 'total') AS total_impact,
    count(*) FILTER (WHERE ssvc_automatable = 'yes' AND ssvc_technical_impact = 'total')
        AS automatable_total,
    count(*) FILTER (WHERE nvd_cvss_v3_base_score IS NOT NULL AND cna_cvss_v3_base_score IS NOT NULL)
        AS cvss_both_scored,
    count(*) FILTER (WHERE cna_cvss_v3_base_score < nvd_cvss_v3_base_score) AS cna_scored_lower,
    count(*) FILTER (WHERE cna_cvss_v3_base_score > nvd_cvss_v3_base_score) AS cna_scored_higher,
    count(*) FILTER (WHERE kev_date_added <= listed_through) AS epss_asked,
    count(epss_before_kev) AS epss_scored,
    count(*) FILTER (WHERE kev_date_added <= listed_through AND epss_before_kev IS NULL)
        AS epss_unscored,
    count(*) FILTER (WHERE epss_before_kev < 0.1) AS epss_under_10pct,
    round(median(epss_before_kev), 4) AS median_epss_before_kev,
    median(days_reserved_before_published) FILTER (WHERE days_reserved_before_published >= 0)
        AS median_days_reserved_before_published,
    'cisa-kev;cve-list;epss;nvd;vendor-resolution' AS sources
FROM by_cve, epss_through
GROUP BY vendor_id, vendor_slug, vendor_name, is_security_vendor
ORDER BY kev_count DESC, slug
