-- How well names from each source resolve: names seen, how many matched a curated vendor or
-- SEC-filing organization, how many distinct entities they came to, and how many stayed
-- unresolved. "kev" is CISA's vendor names, matched by the alias table alone (ledger resolve);
-- the others are matched by the rules in entities.py.
WITH kev AS (
    SELECT
        'kev' AS name_kind,
        (SELECT count(DISTINCT vendor_name) FROM silver.product_mentions) AS names,
        (SELECT count(*) FROM ops.unresolved_vendor_names) AS unresolved,
        (SELECT count(DISTINCT vendor_id) FROM silver.products) AS distinct_entities,
        CAST(NULL AS BIGINT) AS by_alias,
        CAST(NULL AS BIGINT) AS by_cpe,
        CAST(NULL AS BIGINT) AS by_normalized,
        CAST(NULL AS BIGINT) AS by_squashed,
        CAST(NULL AS BIGINT) AS by_prefix
),
linked AS (
    SELECT
        name_kind,
        count(*) AS names,
        count(*) FILTER (WHERE target_id IS NULL) AS unresolved,
        count(DISTINCT target_id) AS distinct_entities,
        count(*) FILTER (WHERE rule = 'alias') AS by_alias,
        count(*) FILTER (WHERE rule = 'cpe') AS by_cpe,
        count(*) FILTER (WHERE rule = 'normalized') AS by_normalized,
        count(*) FILTER (WHERE rule = 'squashed') AS by_squashed,
        count(*) FILTER (WHERE rule = 'prefix') AS by_prefix
    FROM silver.entity_links
    GROUP BY name_kind
)
SELECT
    name_kind,
    names,
    names - unresolved AS resolved,
    unresolved,
    distinct_entities,
    by_alias,
    by_cpe,
    by_normalized,
    by_squashed,
    by_prefix,
    'cisa-kev;cve-list;sec-8k;third-party-review;vendor-resolution' AS sources
FROM (SELECT * FROM kev UNION ALL SELECT * FROM linked)
ORDER BY name_kind
