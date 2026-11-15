-- One row per name another source uses for a company (the CNA that assigned a CVE, a company
-- filing an 8-K, a third party named in a filing), and the curated vendor or SEC-filing
-- organization it resolves to, if any. See pipelines/src/ledger_pipelines/entities.py.
-- confidence is the matching rule's; 0 means the name matched nothing.
SELECT
    l.id AS link_id,
    l.name_kind,
    l.name,
    l.target_id IS NOT NULL AS linked,
    l.target_type,
    l.target_id,
    l.target_key,
    coalesce(v.name, o.name) AS target_name,
    v.is_security_vendor,
    l.rule,
    l.provenance.source_url AS source_url,
    l.provenance.raw_document_id AS raw_document_id,
    l.provenance.crawled_at AS crawled_at,
    l.provenance.parser_id AS parser_id,
    l.provenance.parser_version AS parser_version,
    l.provenance.confidence AS confidence,
    l.provenance.license AS license
FROM silver.entity_links AS l
LEFT JOIN silver.vendors AS v ON l.target_type = 'vendor' AND v.id = l.target_id
LEFT JOIN silver.organizations AS o ON l.target_type = 'org' AND o.id = l.target_id
ORDER BY l.name_kind, l.name
