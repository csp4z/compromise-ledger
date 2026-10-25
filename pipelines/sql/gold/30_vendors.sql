-- One row per curated vendor with its KEV totals; vendors with no KEV entries show zeros.
SELECT
    vendor.id AS vendor_id,
    vendor.slug,
    vendor.name,
    vendor.is_security_vendor,
    count(DISTINCT k.cve_id) AS kev_count,
    count(DISTINCT k.cve_id) FILTER (WHERE k.kev_ransomware_use = 'known') AS kev_ransomware_known,
    count(DISTINCT k.product_id) AS kev_products,
    min(k.kev_date_added) AS first_kev_date,
    max(k.kev_date_added) AS last_kev_date,
    -- Provenance: the vendor list is curated seed data; counts derive from the KEV rows.
    any_value(vendor.provenance.source_url) AS source_url,
    any_value(vendor.provenance.raw_document_id) AS raw_document_id,
    any_value(vendor.provenance.parser_version) AS parser_version,
    any_value(vendor.provenance.license) AS license
FROM silver.vendors AS vendor
LEFT JOIN gold.kev_vendor_products AS k ON k.vendor_id = vendor.id
GROUP BY vendor.id, vendor.slug, vendor.name, vendor.is_security_vendor
ORDER BY kev_count DESC, vendor.slug
