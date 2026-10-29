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
- **Sensitive requests:** if a public issue would itself cause harm, email
  [contact5@kuricove.com](mailto:contact5@kuricove.com) instead. Your request will not be
  published.

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

- Each accepted request becomes a row in [`data/corrections/corrections.csv`](data/corrections/)
  (`suppress` or `amend`), referencing the request, and is committed publicly. A private request
  is referenced only by a case number. Corrections are applied before every gold build, so they
  reach the API, the site, and the downloads with the next daily run.
- The original source data stays in the bronze and silver layers, which are not published, so
  the reason for each change can be audited.
- **Removals also purge history.** Published tables are rebuilt from scratch on every run and
  keep no earlier versions, so a removed record can't be reached through older snapshots. The
  nightly backups hold it until they rotate out, after 7 days.
- A public changelog, the `corrections_log` download, lists each correction by record ID, date,
  and type, without repeating the removed content.

## What this process does not do

- It does not remove facts that are accurately sourced from official public records (such as an
  organization's own SEC filing or a CISA KEV entry) only because they are unflattering.
  It will correct how those facts are represented.
- It does not handle requests to remove data from upstream sources. Contact those sources directly.
