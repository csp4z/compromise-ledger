-- KEV additions per month, and how many affect a security vendor's own products. Totals count
-- every KEV entry, including those whose vendor name is unresolved.
WITH by_cve AS (
    SELECT
        v.cve_id,
        v.kev_date_added,
        coalesce(bool_or(k.is_security_vendor), false) AS security_vendor
    FROM gold.vulnerabilities AS v
    LEFT JOIN gold.kev_vendor_products AS k ON k.vulnerability_id = v.id
    WHERE v.in_kev
    GROUP BY v.cve_id, v.kev_date_added
)
SELECT
    CAST(date_trunc('month', kev_date_added) AS DATE) AS month,
    count(*) AS kev_added,
    count(*) FILTER (WHERE security_vendor) AS security_vendor_kev_added,
    round(count(*) FILTER (WHERE security_vendor) / count(*), 4) AS security_vendor_share,
    'cisa-kev;vendor-resolution' AS sources
FROM by_cve
GROUP BY month
ORDER BY month
