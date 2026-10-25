-- Headline comparison: security vendors' own products vs everyone else's, one row per group.
-- Time to KEV counts only CVEs published on or after the catalog's launch (2021-11-03): the
-- launch added a backlog of old CVEs, which would otherwise dominate the medians.
WITH by_cve AS (
    SELECT
        v.cve_id,
        v.days_to_kev,
        v.kev_ransomware_use,
        v.published >= TIMESTAMPTZ '2021-11-03 00:00:00+00' AS recent,
        coalesce(bool_or(k.is_security_vendor), false) AS security_vendor
    FROM gold.vulnerabilities AS v
    LEFT JOIN gold.kev_vendor_products AS k ON k.vulnerability_id = v.id
    WHERE v.in_kev
    GROUP BY v.cve_id, v.published, v.days_to_kev, v.kev_ransomware_use
)
SELECT
    CASE WHEN security_vendor THEN 'security_vendors' ELSE 'all_other_vendors' END AS vendor_group,
    count(*) AS kev_count,
    count(*) FILTER (WHERE kev_ransomware_use = 'known') AS ransomware_known,
    round(count(*) FILTER (WHERE kev_ransomware_use = 'known') / count(*), 4) AS ransomware_share,
    count(*) FILTER (WHERE recent) AS recent_cves,
    median(days_to_kev) FILTER (WHERE recent) AS median_days_to_kev,
    quantile_cont(days_to_kev, 0.25) FILTER (WHERE recent) AS p25_days_to_kev,
    quantile_cont(days_to_kev, 0.75) FILTER (WHERE recent) AS p75_days_to_kev,
    round(count(*) FILTER (WHERE recent AND days_to_kev <= 7) / count(*) FILTER (WHERE recent), 4)
        AS share_within_7_days,
    DATE '2021-11-03' AS time_to_kev_published_since,
    'cisa-kev;nvd;vendor-resolution' AS sources
FROM by_cve
GROUP BY security_vendor
ORDER BY vendor_group DESC
