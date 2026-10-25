-- One row per KEV entry and affected vendor product: the main fact table for the site.
SELECT
    v.cve_id,
    v.id AS vulnerability_id,
    vendor.id AS vendor_id,
    vendor.slug AS vendor_slug,
    vendor.name AS vendor_name,
    vendor.is_security_vendor,
    product.id AS product_id,
    product.name AS product_name,
    v.kev_date_added,
    v.kev_due_date,
    v.kev_ransomware_use,
    v.published,
    v.days_to_kev,
    -- Provenance of the product-to-CVE link (the source that named the product).
    r.provenance.source_url AS source_url,
    r.provenance.raw_document_id AS raw_document_id,
    r.provenance.crawled_at AS crawled_at,
    r.provenance.parser_id AS parser_id,
    r.provenance.parser_version AS parser_version,
    r.provenance.confidence AS confidence,
    r.provenance.license AS license
FROM silver.relationships AS r
JOIN silver.products AS product ON product.id = r.source_ref
JOIN silver.vendors AS vendor ON vendor.id = product.vendor_id
JOIN gold.vulnerabilities AS v ON v.id = r.target_ref
WHERE r.relationship_type = 'has' AND v.in_kev
ORDER BY v.kev_date_added DESC, v.cve_id, vendor.slug, product.name
