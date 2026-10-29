-- One row per SEC filing that discloses a cybersecurity incident, with the incident it belongs to.
-- A company's filings are one incident when:
--   - an amendment (8-K/A) follows an original filing: it joins the latest incident;
--   - an original 8-K comes within 90 days of the company's previous original: companies often
--     report under Item 8.01 first and file under 1.05 once they judge the incident material.
-- Otherwise a filing starts a new incident. An incident's ID is its first filing's ID.
WITH filings AS (
    SELECT
        i.*,
        o.name AS organization_name,
        o.sec_cik,
        o.tickers,
        i.sec_form = '8-K' AS original
    FROM silver.incidents AS i
    JOIN silver.organizations AS o ON o.id = i.organization_id
),
flagged AS (
    SELECT
        *,
        CASE
            WHEN previous_original IS NULL THEN 1
            WHEN original AND date_diff('day', previous_original, disclosed_on) > 90 THEN 1
            ELSE 0
        END AS starts_incident
    FROM (
        SELECT
            *,
            max(CASE WHEN original THEN disclosed_on END) OVER (
                PARTITION BY organization_id
                ORDER BY disclosed_on, original DESC, sec_accession
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS previous_original
        FROM filings
    )
),
grouped AS (
    SELECT
        *,
        sum(starts_incident) OVER (
            PARTITION BY organization_id
            ORDER BY disclosed_on, original DESC, sec_accession
        ) AS sequence
    FROM flagged
)
SELECT
    first_value(id) OVER (
        PARTITION BY organization_id, sequence
        ORDER BY disclosed_on, original DESC, sec_accession
    ) AS incident_id,
    id AS filing_id,
    organization_id,
    organization_name,
    sec_cik,
    array_to_string(tickers, ';') AS tickers,
    status,
    disclosed_on,
    sec_form,
    sec_item,
    sec_accession,
    provenance.source_url AS source_url,
    provenance.raw_document_id AS raw_document_id,
    provenance.crawled_at AS crawled_at,
    provenance.parser_id AS parser_id,
    provenance.parser_version AS parser_version,
    provenance.confidence AS confidence,
    provenance.license AS license
FROM grouped
ORDER BY disclosed_on DESC, organization_name, sec_accession
