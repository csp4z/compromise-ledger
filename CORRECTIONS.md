# Corrections and takedown process

This dataset names real organizations, so every record has to be accurate, sourced, and
correctable. This document describes how to request a change and what happens next.

## What you can request

- **Correction:** a fact is wrong (date, vendor or product attribution, CVE mapping, organization name).
- **Status change:** a record should move to `reported` or `confirmed`, or be flagged `disputed` or `retracted`
  (see the status scale in [docs/DATA_POLICY.md](docs/DATA_POLICY.md#claims-vs-confirmed-facts)).
- **Removal:** a record should not be published, for example because it identifies an individual
  rather than an organization or relies on a source that has been withdrawn.

## How to request

- **Public requests:** open a
  [correction request](https://github.com/csp4z/compromise-ledger/issues/new?template=correction.yml).
  Include the record ID or page URL, what is wrong, and supporting evidence (a link is enough).
- **Sensitive requests:** if a public issue would itself cause harm, use the private contact
  address instead. Your request will not be published. The address will be added here before the
  dataset is first published.

## What happens next

| Step | Target |
|---|---|
| Acknowledge the request | 5 business days |
| Decide (accept, partially accept, or decline with reasons) | 14 days |
| Apply an accepted change to the next published build | 2 days after the decision |

While a request is reviewed, a disputed **leak-site claim** is suppressed from public output by
default. Records from government or regulatory sources (CISA, NVD, SEC) stay visible while
under review, marked as disputed.

## How changes are applied

- Each accepted request becomes a row in `silver.corrections` (`suppress` or `amend`), referencing
  the request. Corrections are applied before any gold build, API response, or export.
- The original source data stays in the bronze layer, so the reason for each change can be audited.
- **Removals also purge history.** Iceberg keeps snapshots for time travel, so after a removal,
  snapshots containing the removed record are expired and the affected exports are rebuilt.
  Without this, the "removed" data would stay reachable through older snapshots.
- A public changelog lists each correction by record ID, date, and type, without repeating the
  removed content.

## What this process does not do

- It does not remove facts that are accurately sourced from official public records (such as an
  organization's own SEC filing or a CISA KEV entry) only because they are unflattering.
  It will correct how those facts are represented.
- It does not handle requests to remove data from upstream sources. Contact those sources directly.
