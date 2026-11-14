-- One row per vulnerability, merged across sources. Each field comes from the most confident
-- source that has it. NVD fields (published, CVSS) are null for a CVE NVD hasn't returned.
--
-- From the CVE List: who assigned the CVE, when it was reserved, the assigning CNA's own CVSS
-- score next to NVD's own (each null where that party gave none), and CISA's SSVC decision
-- points. From EPSS: the score on the day before the KEV listing, the model's last estimate
-- made without knowing of the listing. It is null when the CVE had no score that day, which
-- for a listed CVE usually means it was not public yet.
WITH merged AS (
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
        list_distinct(list(provenance.parser_id)) AS parser_ids,
        list_distinct(list(provenance.source_url)) AS urls,
        list_distinct(list(provenance.raw_document_id)) AS document_ids,
        max(provenance.crawled_at) AS crawled_at,
        max(provenance.confidence) AS confidence,
        list_distinct(list(provenance.license)) AS license_ids,
        arg_max(cve_assigner, provenance.confidence) FILTER (WHERE cve_assigner IS NOT NULL) AS cve_assigner,
        min(cve_reserved) AS cve_reserved,
        max(cvss_v3_base_score) FILTER (WHERE cvss_v3_scorer = 'nvd') AS nvd_cvss_v3_base_score,
        max(cvss_v3_base_score) FILTER (WHERE cvss_v3_scorer = 'cna') AS cna_cvss_v3_base_score,
        arg_max(ssvc_exploitation, provenance.confidence) FILTER (WHERE ssvc_exploitation IS NOT NULL) AS ssvc_exploitation,
        arg_max(ssvc_automatable, provenance.confidence) FILTER (WHERE ssvc_automatable IS NOT NULL) AS ssvc_automatable,
        arg_max(ssvc_technical_impact, provenance.confidence) FILTER (WHERE ssvc_technical_impact IS NOT NULL) AS ssvc_technical_impact
    FROM silver.vulnerabilities
    GROUP BY id, cve_id
)
SELECT
    m.id,
    m.cve_id,
    m.description,
    m.published,
    m.last_modified,
    m.cvss_v3_base_score,
    m.cvss_v3_severity,
    m.cwe_ids,
    m.in_kev,
    m.kev_date_added,
    m.kev_due_date,
    m.kev_ransomware_use,
    m.days_to_kev,
    array_to_string(list_sort(m.parser_ids || coalesce([e.provenance.parser_id], [])), ';') AS sources,
    array_to_string(list_sort(m.urls || coalesce([e.provenance.source_url], [])), ';') AS source_urls,
    array_to_string(list_sort(m.document_ids || coalesce([e.provenance.raw_document_id], [])), ';')
        AS raw_document_ids,
    greatest(m.crawled_at, coalesce(e.provenance.crawled_at, m.crawled_at)) AS crawled_at,
    m.confidence,
    array_to_string(list_sort(list_distinct(m.license_ids || coalesce([e.provenance.license], []))), ';')
        AS licenses,
    m.cve_assigner,
    m.cve_reserved,
    date_diff('day', CAST(m.cve_reserved AS DATE), CAST(m.published AS DATE)) AS days_reserved_before_published,
    m.nvd_cvss_v3_base_score,
    m.cna_cvss_v3_base_score,
    m.ssvc_exploitation,
    m.ssvc_automatable,
    m.ssvc_technical_impact,
    e.epss AS epss_before_kev,
    e.percentile AS epss_percentile_before_kev,
    e.score_date AS epss_score_date
FROM merged AS m
LEFT JOIN silver.epss_scores AS e
    ON e.vulnerability_id = m.id AND e.score_date = m.kev_date_added - 1
ORDER BY m.cve_id
