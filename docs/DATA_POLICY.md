# Data Policy

Compromise Ledger is a reference dataset about security incidents and vendor product flaws. It is **not** a source of breached data, and it is designed so that it can never become one.

## What we collect

- **Incident metadata:** affected organization, sector, dates (occurred, disclosed, reported), attack type, claimed or attributed threat actor.
- **Vendor and product metadata:** vendor, product, version ranges, advisory identifiers, CVEs, known exploitation status.
- **Provenance:** source URL (or, for leak sites, a hash of the post URL), source type, crawl timestamp, parser version, upstream license, and confidence score for every fact.
- **Third-party advisory text:** vendor advisories are copyrighted. We store structured metadata and a link to the original, not a republished copy of the text.

## What we never collect

- Leaked files, data dumps, samples, screenshots of stolen data, or download links to any of them.
- Personal information about individuals affected by an incident.
- Credentials, secrets, or access details of any kind.
- Content from leak sites beyond the listing metadata above.

Crawlers are built so that downloading leaked files is not possible by design, not merely by policy: they parse listing pages only and do not follow file links.

## Claims vs. confirmed facts

Threat-actor leak-site posts are frequently exaggerated, recycled, or false. Each incident carries a status:

| Status | Meaning |
| --- | --- |
| **Claimed** | Asserted by a threat actor; not independently corroborated. |
| **Reported** | Reported by credible media or researchers. |
| **Confirmed** | Acknowledged by the organization, a regulator filing, or an official notice. |

Status only moves forward when a qualifying source is added, and that source is shown alongside it.

Two further flags can apply at any status:

| Flag | Meaning |
| --- | --- |
| **Disputed** | The organization or a credible source contests the record. It is shown with the dispute; disputed leak-site claims are hidden while under review. |
| **Retracted** | The original source withdrew the claim. The record is removed from published data, and the change is logged. |

## Confidence scores

Each fact carries a confidence score based on source type and the number of independent corroborating sources. The scoring method is documented in the repository and versioned with the code.

## Corrections and takedowns

Anyone may request a correction or review of an entry:

1. Open an issue using the corrections template, or use the private contact in [CORRECTIONS.md](../CORRECTIONS.md) if a public issue would cause harm.
2. Include the entry and the reason (inaccurate, outdated, misattributed).
3. Requests are acknowledged within 5 business days and decided within 14 days; outcomes are logged publicly without exposing private details of the requester.

Entries that are accurate and sourced from public records are generally retained, but may be updated, re-labeled, or annotated with the organization's response. A removal also expires the historical table snapshots that contain the record, so it is not reachable through time travel. The full process is in [CORRECTIONS.md](../CORRECTIONS.md).

## Dark-web collection safeguards

- Tor crawlers run in a network-isolated container with egress only through Tor.
- They read listing pages only; no file downloads, no interaction with actors, no payments, no accounts.
- They extract only an allowlisted set of metadata fields, accept HTML responses only, and enforce a response-size cap.
- Post URLs are stored as hashes and never published as links.
- Collection follows the hosting provider's acceptable-use policy.

## Clearnet crawling etiquette

Every crawler declares its rate limit, identifies itself with a User-Agent that includes a contact address, honors robots.txt and the source's terms of use, and records the source's license with each fact.

## Dataset license

The dataset is licensed under [CC BY 4.0](../LICENSE-DATA). Upstream sources keep their own terms, which are recorded in each record's provenance. Users of the dataset are expected to preserve source attribution and status labels.
