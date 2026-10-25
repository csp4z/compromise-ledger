-- One row per vulnerability, merged across sources. Each field comes from the most confident
-- source that has it. NVD fields (published, CVSS) stay null until the NVD crawler lands.
SELECT
    id,
    cve_id,
    arg_max(description, provenance.confidence) FILTER (WHERE description IS NOT NULL) AS description,
    min(published) AS published,
    max(last_modified) AS last_modified,
    arg_max(cvss_v3_base_score, provenance.confidence) FILTER (WHERE cvss_v3_base_score IS NOT NULL) AS cvss_v3_base_score,
    arg_max(cvss_v3_severity, provenance.confidence) FILTER (WHERE cvss_v3_severity IS NOT NULL) AS cvss_v3_severity,
    arg_max(array_to_string(cwe_ids, ';'), provenance.confidence) FILTER (WHERE len(cwe_ids) > 0) AS cwe_ids,
    min(kev_date_added) IS NOT NULL AS in_kev,
    min(kev_date_added) AS kev_date_added,
    min(kev_due_date) AS kev_due_date,
    arg_max(kev_ransomware_use, provenance.confidence) FILTER (WHERE kev_ransomware_use IS NOT NULL) AS kev_ransomware_use,
    min(kev_date_added) - CAST(min(published) AS DATE) AS days_to_kev,
    -- Provenance, one value per contributing source.
    string_agg(DISTINCT provenance.parser_id, ';' ORDER BY provenance.parser_id) AS sources,
    string_agg(DISTINCT provenance.source_url, ';' ORDER BY provenance.source_url) AS source_urls,
    string_agg(DISTINCT provenance.raw_document_id, ';' ORDER BY provenance.raw_document_id) AS raw_document_ids,
    max(provenance.crawled_at) AS crawled_at,
    max(provenance.confidence) AS confidence,
    string_agg(DISTINCT provenance.license, ';' ORDER BY provenance.license) AS licenses
FROM silver.vulnerabilities
GROUP BY id, cve_id
ORDER BY cve_id
