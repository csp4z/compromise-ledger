# Fixtures

Real responses from FIRST's EPSS API (`https://api.first.org/data/v1/epss?cve=...&date=...`),
recorded 2026-11-13 and kept as returned. Each asks for the CVEs
CISA added to KEV on one day, scored the day before.

- `2024-06-25.json`: CVE-2020-13965, CVE-2022-24816, CVE-2022-2586 (listed 2024-06-26). All
  three were long public and have scores.
- `2024-07-08.json`: CVE-2024-23692, CVE-2024-38080, CVE-2024-38112 (listed 2024-07-09). Only
  the first has a score; the other two were published on the day they were listed.
- `2024-01-09.json`: CVE-2023-46805, CVE-2024-21887 (listed 2024-01-10). Neither was public
  yet, so the page is empty.
