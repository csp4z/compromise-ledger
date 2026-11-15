# ADR 0008: Group organization names by rule; probabilistic linkage waits for richer records

- **Status:** Accepted
- **Date:** 2026-11-15

## Context

Entity resolution began with a few hundred names matched by exact rules (`entities.py`, roadmap
Phase 2 step 4). Breach notices are the first source with thousands of free-text organization
names and no shared ID: 1,698 notices carrying 1,612 distinct names. The same organization
files under spelling variants, with a supplier in brackets, under a trade name, or as an
"(Amended Notice)". [ARCHITECTURE.md](../ARCHITECTURE.md) plans "fuzzy and embedding-based
matching" for this.

The standard tool for it is probabilistic record linkage, and [Splink](https://moj-analytical-services.github.io/splink/)
(MIT, runs on DuckDB) fits the stack. It was tried before being adopted.

**The trial (2026-11-15).** 2,047 records: the notices, the 93 SEC filers, and the 283 curated
vendors. The model compared the name in levels (equal, core names equal, one name's distinctive
words within the other's, different), plus state and industry, with weights trained by
expectation maximisation. 131 distinct candidate pairs came back; 125 were labelled by hand
(115 the same organization, 10 different, 6 left out as unclear).

| Method | True matches | False matches | Missed | Precision | Recall |
|---|---|---|---|---|---|
| Core names equal (a rule) | 109 | 0 | 6 | 1.000 | 0.948 |
| Cleaned names equal (a rule) | 90 | 0 | 25 | 1.000 | 0.783 |
| Splink, probability ≥ 0.5 | 104 | 5 | 11 | 0.954 | 0.904 |
| Splink, probability ≥ 0.9 | 38 | 2 | 77 | 0.950 | 0.330 |

Splink did worse than the rule at every threshold, and below the project's precision bar of
0.98 (a false merge misattributes an incident). The reasons are in the data, not the tool:

- **Too few fields.** A notice has a name, a state, and an industry label. SEC filers and
  vendors have only a name. Probabilistic linkage earns its keep by weighing several
  independent fields; here the name decides almost everything.
- **The state field is noisy.** Identical names filed from different states scored as low as
  0.03, while two different housing authorities in the same state scored 0.93.
- **The hard cases need knowledge, not similarity.** A law firm filing "on behalf of" a client,
  a university and its foundation, a company and a credit union named after it: a similarity
  score puts these near real matches.

The labelled set is small and its negatives are few (10), and the labels are one person's
reading, so the table shows a clear ordering rather than precise rates.

## Decision

- **Group breach-notice names by core name, a rule** (`pipelines/src/ledger_pipelines/names.py`):
  the name without bracketed asides, trade names ("d/b/a"), or notice labels, then normalized as
  for other names. Names with the same core name are the same organization. Names that only
  share words are not grouped.
- **Link notifiers to vendors and SEC filers with the same rule**, as a sixth rule (`core`) in
  `entities.py`, used for breach-notice names only. The rules measured for the Phase 2 gate are
  unchanged for other names.
- **Splink is not added.** Revisit when a source brings records with at least three usable
  fields beyond the name (an address, a registration or tax ID, dates, a website), or when the
  rule's recall on a labelled set falls below 0.9. Re-run this comparison first.
- **Notifier names stay unpublished.** Links and groups are stored in `silver.entity_links`;
  gold publishes counts only (`breach_notifier_summary`, `entity_resolution_summary`). The
  labelled pairs contain notifier names, so they live in `.private/`, outside Git, and their test
  is skipped where the file is absent.

## Consequences

- Every match can be explained in a sentence, and nothing statistical has to be retrained or
  monitored.
- Six known pairs are missed (a typo in a legal form, "Hotels" against "Hotels and Resorts", a
  name with a second party after a slash). They can only be recovered by curated aliases or by
  a later, richer source.
- First results, 2026-11-15: 1,698 notices come from 1,583 organizations; 78 filed more than
  once (166 notices, at most 4 each); 17 companies that disclosed an incident to the SEC also
  filed a Washington notice; 27 notices have a withheld name and can't be grouped.
- The measurement can't run in CI, because the labels can't be published. The numbers above are
  the record; anyone with the labels can re-run `test_notifier_linkage_private.py`.
- Bracketed text in a notice name sometimes names a person. It is dropped from the core name
  and never published, but it is still in silver; the parser's withholding rule should be
  extended to brackets before any name is published.
