# Fixtures

Real NVD CVE API 2.0 responses (`hasKev` queries, recorded 2026-10-25), trimmed to five records
split across two pages so the tests exercise paging. `startIndex`, `resultsPerPage`, and
`totalResults` are set to match the trimmed pages; record contents are unchanged (only
re-indented).

- `page-0.json`, `page-1.json`: a full fetch (CVE-2002-0367, CVE-2004-0210, CVE-2024-21762,
  CVE-2021-3199, CVE-2023-22894).
- `empty.json`: a query with no results.

Rare shapes (CVSS 3.0 only, no CVSS, Rejected status) are made in the tests by editing copies,
so these files stay real data. To refresh, re-record with the same query and keep
records covering the same cases.
