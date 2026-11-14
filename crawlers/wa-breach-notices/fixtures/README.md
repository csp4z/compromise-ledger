# Fixtures

`notices.json`: 16 real rows of the Washington Attorney General's breach-notification dataset
(`https://data.wa.gov/resource/sb4j-ca4h.json`), recorded 2026-11-13. Rows are unchanged; the
selection covers every cause and attack type, missing dates, a missing resident count, state
values that are not two-letter codes (`"WA "`, `"Iowa"`), a breach dated after the organization
became aware of it, and a name with a professional-practice marker.

`empty.json`: a query with no rows.

Other cases (an unknown cause, a full page) are made in the tests by editing copies.
