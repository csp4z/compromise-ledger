-- The same measures as 90_breach_notice_yearly.sql over all years, by one dimension at a time:
-- the Attorney General's industry label, the cause, and for cyberattacks the kind of attack.
-- Aggregates only.
WITH notices AS (
    SELECT
        *,
        CASE WHEN aware_on >= breach_started_on THEN aware_on - breach_started_on END AS days_to_discover,
        CASE WHEN submitted_on >= aware_on THEN submitted_on - aware_on END AS days_to_notify
    FROM silver.breach_notices
),
labelled AS (
    SELECT 'industry' AS dimension, coalesce(industry, 'Not stated') AS label, * FROM notices
    UNION ALL
    SELECT 'cause', coalesce(cause, 'not-stated'), * FROM notices
    UNION ALL
    SELECT 'attack_type', coalesce(attack_type, 'not-stated'), * FROM notices WHERE cause = 'cyberattack'
)
SELECT
    dimension,
    label,
    count(*) AS notices,
    count(*) FILTER (WHERE attack_type = 'ransomware') AS ransomware,
    round(count(*) FILTER (WHERE attack_type = 'ransomware') / count(*), 4) AS ransomware_share,
    count(days_to_discover) AS discover_measured,
    median(days_to_discover) AS median_days_to_discover,
    count(days_to_notify) AS notify_measured,
    median(days_to_notify) AS median_days_to_notify,
    round(count(*) FILTER (WHERE days_to_notify > 30) / nullif(count(days_to_notify), 0), 4)
        AS share_notified_after_30_days,
    CAST(sum(residents_affected) AS BIGINT) AS residents_affected,
    min(submitted_on) AS first_notice_on,
    max(submitted_on) AS latest_notice_on,
    'wa-breach-notices' AS sources
FROM labelled
GROUP BY dimension, label
ORDER BY dimension, notices DESC, label
