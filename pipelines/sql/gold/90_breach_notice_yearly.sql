-- Breach notifications filed with the Washington Attorney General, per calendar year of filing.
-- Aggregates only: no table names the notifying organizations (see DATA_POLICY.md).
-- days_to_discover: breach start to the day the organization became aware.
-- days_to_notify: becoming aware to the notice reaching the Attorney General.
-- Both use the dates the organization reported, and leave out a notice whose dates are
-- missing or out of order. The latest year is partial.
WITH notices AS (
    SELECT
        *,
        CASE WHEN aware_on >= breach_started_on THEN aware_on - breach_started_on END AS days_to_discover,
        CASE WHEN submitted_on >= aware_on THEN submitted_on - aware_on END AS days_to_notify
    FROM silver.breach_notices
)
SELECT
    CAST(year(submitted_on) AS INTEGER) AS year,
    count(*) AS notices,
    count(*) FILTER (WHERE cause = 'cyberattack') AS cyberattacks,
    count(*) FILTER (WHERE attack_type = 'ransomware') AS ransomware,
    round(count(*) FILTER (WHERE attack_type = 'ransomware') / count(*), 4) AS ransomware_share,
    count(days_to_discover) AS discover_measured,
    median(days_to_discover) AS median_days_to_discover,
    count(days_to_notify) AS notify_measured,
    median(days_to_notify) AS median_days_to_notify,
    round(count(*) FILTER (WHERE days_to_notify > 30) / nullif(count(days_to_notify), 0), 4)
        AS share_notified_after_30_days,
    CAST(sum(residents_affected) AS BIGINT) AS residents_affected,
    max(submitted_on) AS latest_notice_on,
    'wa-breach-notices' AS sources
FROM notices
GROUP BY year
ORDER BY year
