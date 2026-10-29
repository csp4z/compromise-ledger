-- One row per incident: a company's grouped 8-K filings (see 75_incident_filings.sql).
-- material: at least one filing is under Item 1.05, which a company uses once it has determined
-- the incident is material. The others were disclosed under Item 8.01 only.
SELECT
    incident_id,
    any_value(organization_id) AS organization_id,
    any_value(organization_name) AS organization_name,
    any_value(sec_cik) AS sec_cik,
    any_value(tickers) AS tickers,
    any_value(status) AS status,
    min(disclosed_on) AS first_disclosed_on,
    max(disclosed_on) AS last_filed_on,
    count(*) AS filings,
    bool_or(sec_item = '1.05') AS material,
    max(confidence) AS confidence,
    arg_min(source_url, disclosed_on) AS source_url,
    string_agg(sec_accession, ';' ORDER BY disclosed_on, sec_accession) AS sec_accessions,
    'sec-8k' AS sources,
    any_value(license) AS license
FROM gold.incident_filings
GROUP BY incident_id
ORDER BY first_disclosed_on DESC, organization_name
