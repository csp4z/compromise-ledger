-- One row per curated vendor with an NVD CPE vendor name: how many CVEs NVD matches to the vendor
-- by CPE, how many of those are in KEV, and the share that reached KEV. Both counts are matched
-- the same way, so they compare with each other; kev_count in gold.vendors comes from KEV's own
-- vendor names and can differ slightly.
WITH counts AS (
    SELECT
        cpe_vendor,
        any_value(cve_count) FILTER (WHERE scope = 'all') AS nvd_cve_count,
        any_value(cve_count) FILTER (WHERE scope = 'kev') AS nvd_kev_count,
        -- The older of the two counts, so the date never overstates freshness.
        min(provenance.crawled_at) AS counted_at
    FROM silver.cve_counts
    GROUP BY cpe_vendor
)
SELECT
    vendor.id AS vendor_id,
    vendor.slug,
    vendor.name,
    vendor.is_security_vendor,
    vendor.cpe_vendor,
    c.nvd_cve_count,
    c.nvd_kev_count,
    CASE WHEN c.nvd_cve_count > 0 THEN round(c.nvd_kev_count / c.nvd_cve_count, 4) END
        AS kev_share,
    c.counted_at,
    'nvd-cve-counts;vendor-resolution' AS sources
FROM silver.vendors AS vendor
JOIN counts AS c ON c.cpe_vendor = vendor.cpe_vendor
WHERE c.nvd_cve_count IS NOT NULL AND c.nvd_kev_count IS NOT NULL
ORDER BY kev_share DESC NULLS LAST, vendor.slug
