-- Vendor names that no seed entry matches. Published so the gaps in the counts are visible.
SELECT
    vendor_name,
    mentions,
    array_to_string(parser_ids, ';') AS sources
FROM ops.unresolved_vendor_names
ORDER BY mentions DESC, vendor_name
