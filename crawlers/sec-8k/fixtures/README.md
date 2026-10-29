# Fixtures

Real EDGAR full-text search responses (`efts.sec.gov/LATEST/search-index`), recorded 2026-10-28
and kept as returned.

- `identified-incident-8k.json`: `q="identified a cybersecurity incident"`, `forms=8-K`,
  2023-12-18 to 2026-10-27. 15 hits: Item 1.05 and 8.01 disclosures, an 8.01 filing later
  followed by a 1.05 one for the same incident, 7.01 updates, and a financing exhibit.
- `cybersecurity-incident-8k.json`: `q="cybersecurity incident"`, `forms=8-K`, 2026-09-01 to
  2026-10-27. 61 hits, mostly false matches (merger-agreement warranties, earnings releases,
  press releases, policy exhibits). The crawler no longer searches this phrase; the file tests
  that the parser drops exhibits and filings about other business.
- `item-105-8ka.json`: `q="Item 1.05"`, `forms=8-K/A`, 2023-12-18 to 2026-10-27. 26 amendments.
- `empty.json`: a search with no hits.

Paging and over-limit cases are made in the tests by editing copies, so these files stay real
data. To refresh, re-record the same queries with a `Compromise Ledger <email>` User-Agent; the
classification test names the filings it expects, so update it with the new hits.
