-- The same signals as 62_vendor_signals.sql, for the two groups: security vendors' own products
-- against everyone else's. Every KEV entry counts once, including those whose vendor name is
-- unresolved (they fall in the second group, as in 60_security_vendor_summary.sql).
WITH by_cve AS (
    SELECT
        v.cve_id,
        any_value(v.kev_date_added) AS kev_date_added,
        any_value(v.ssvc_automatable) AS ssvc_automatable,
        any_value(v.ssvc_technical_impact) AS ssvc_technical_impact,
        any_value(v.nvd_cvss_v3_base_score) AS nvd_score,
        any_value(v.cna_cvss_v3_base_score) AS cna_score,
        any_value(v.epss_before_kev) AS epss,
        any_value(v.days_reserved_before_published) AS days_reserved,
        coalesce(bool_or(k.is_security_vendor), false) AS security_vendor
    FROM gold.vulnerabilities AS v
    LEFT JOIN gold.kev_vendor_products AS k ON k.vulnerability_id = v.id
    WHERE v.in_kev
    GROUP BY v.cve_id
),
epss_through AS (
    SELECT max(score_date) + 1 AS listed_through FROM silver.epss_scores
)
SELECT
    CASE WHEN security_vendor THEN 'security_vendors' ELSE 'all_other_vendors' END AS vendor_group,
    count(*) AS kev_count,
    count(ssvc_automatable) AS ssvc_assessed,
    count(*) FILTER (WHERE ssvc_automatable = 'yes') AS automatable,
    count(*) FILTER (WHERE ssvc_technical_impact = 'total') AS total_impact,
    count(*) FILTER (WHERE ssvc_automatable = 'yes' AND ssvc_technical_impact = 'total')
        AS automatable_total,
    round(count(*) FILTER (WHERE ssvc_automatable = 'yes' AND ssvc_technical_impact = 'total')
        / nullif(count(ssvc_automatable), 0), 4) AS automatable_total_share,
    count(*) FILTER (WHERE nvd_score IS NOT NULL AND cna_score IS NOT NULL) AS cvss_both_scored,
    count(*) FILTER (WHERE cna_score < nvd_score) AS cna_scored_lower,
    count(*) FILTER (WHERE cna_score > nvd_score) AS cna_scored_higher,
    round(count(*) FILTER (WHERE cna_score < nvd_score)
        / nullif(count(*) FILTER (WHERE nvd_score IS NOT NULL AND cna_score IS NOT NULL), 0), 4)
        AS cna_scored_lower_share,
    count(*) FILTER (WHERE kev_date_added <= listed_through) AS epss_asked,
    count(epss) AS epss_scored,
    count(*) FILTER (WHERE kev_date_added <= listed_through AND epss IS NULL) AS epss_unscored,
    round(count(*) FILTER (WHERE kev_date_added <= listed_through AND epss IS NULL)
        / nullif(count(*) FILTER (WHERE kev_date_added <= listed_through), 0), 4)
        AS epss_unscored_share,
    count(*) FILTER (WHERE epss < 0.1) AS epss_under_10pct,
    round(count(*) FILTER (WHERE epss < 0.1) / nullif(count(epss), 0), 4) AS epss_under_10pct_share,
    round(median(epss), 4) AS median_epss_before_kev,
    median(days_reserved) FILTER (WHERE days_reserved >= 0) AS median_days_reserved_before_published,
    'cisa-kev;cve-list;epss;nvd;vendor-resolution' AS sources
FROM by_cve, epss_through
GROUP BY security_vendor
ORDER BY vendor_group DESC
