# Fixtures

`known_exploited_vulnerabilities.json` is a recorded copy of the live feed (catalog version
2026.10.23), trimmed to six real entries so it stays small. `count` is set to match. The
entries were chosen for edge cases: known ransomware use, an empty `cwes` list, a vendor name
with trailing whitespace, a product name with a narrow no-break space, and a non-ASCII vendor.

To refresh: download the feed, keep entries that cover the same cases, and update `count`.
