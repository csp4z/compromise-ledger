-- Who files breach notices, as counts only (no notifier is named; see DATA_POLICY.md).
-- Notices from the same organization are grouped by core name (names.py, ADR 0008): the name
-- without bracketed asides, trade names, or "amended notice". Notices whose name was withheld
-- at parse time can't be grouped and are counted apart.
WITH notices AS (
    SELECT n.id, l.group_id, l.target_type, l.target_id
    FROM silver.breach_notices AS n
    LEFT JOIN silver.entity_links AS l
        ON l.name_kind = 'breach-notice' AND l.name = n.organization_name
),
notifiers AS (
    SELECT
        group_id,
        count(*) AS notices,
        any_value(target_type) AS target_type,
        any_value(target_id) AS target_id
    FROM notices
    WHERE group_id IS NOT NULL
    GROUP BY group_id
)
SELECT
    (SELECT count(*) FROM notices) AS notices,
    (SELECT count(*) FROM notices WHERE group_id IS NULL) AS notices_name_withheld,
    count(*) AS notifiers,
    count(*) FILTER (WHERE notices > 1) AS repeat_notifiers,
    CAST(coalesce(sum(notices) FILTER (WHERE notices > 1), 0) AS BIGINT) AS notices_from_repeat_notifiers,
    max(notices) AS most_notices_by_one_notifier,
    count(*) FILTER (WHERE target_type = 'org') AS notifiers_that_file_with_sec,
    count(*) FILTER (WHERE target_type = 'vendor') AS notifiers_that_are_vendors,
    -- Companies with an SEC-disclosed incident that also filed a breach notice.
    (
        SELECT count(DISTINCT i.organization_id)
        FROM silver.incidents AS i
        JOIN notifiers AS x ON x.target_type = 'org' AND x.target_id = i.organization_id
    ) AS sec_incident_companies_with_a_notice,
    'sec-8k;vendor-resolution;wa-breach-notices' AS sources
FROM notifiers
