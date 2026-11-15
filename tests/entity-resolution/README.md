# Entity resolution: frozen snapshot and labelled set

The measurement behind the Phase 2 gate (docs/ROADMAP.md): entity resolution must reach a
precision of at least 0.98 and beat the alias table's recall, on a frozen snapshot with
hand-labelled names. `pipelines/tests/test_entity_resolution.py` runs it; `pytest -s` prints the
scores.

## What is frozen (2026-11-15)

- `pairs.csv`: every name the published data held on 2026-11-15, labelled. 111 CNA short names
  (the organization that assigned each KEV CVE), 93 SEC filers, and 1 third party named in a
  filing.
- `organizations.csv`: the SEC filers (CIK and name) that names can resolve to.
- `seeds/`: copies of `data/seeds/vendors.csv` and `vendor_aliases.csv` as of that date, so later
  seed changes don't move the measurement.

Change these files only to fix a wrong label, or to take a new snapshot on purpose (and say so
in the commit). Never edit them to make the test pass.

## Labels

`expected` is the entity a name stands for, or empty for none:

- `vendor:<slug>`: a curated vendor. The same organization, or a team or division acting under
  its name (Chrome, `google_android`, and `Google_Devices` are Google; NetScaler is Citrix;
  `facebook` is Meta Platforms). A company acquired before the record keeps its own identity
  only if it has its own vendor row (Symantec does; Pivotal and Trellix don't, so they are none,
  not VMware or McAfee).
- `org:<cik>`: an SEC filer, for third parties that have no vendor row (Evertec).
- empty: no curated vendor or filer. CERTs, bug-bounty platforms, research firms, and the CVE
  Program itself are always none (`mitre`, `hackerone`, `zdi`, `certcc`). So are companies with a
  confusable name (META MATERIALS is not Meta Platforms; SONIC AUTOMOTIVE is not SonicWall;
  `rapid7` assigned a Fortra CVE but is not Fortra).

`evidence` gives the reason: the CVE Program's partner list (`organizationName` for the CNA's
short name), the vendors named on the KEV CVEs the CNA assigned, or the filer's CIK.

## Scoring

A prediction is a true positive when it names the expected entity, a false positive when it
names any other entity (or any entity when none is expected), and a false negative when it names
nothing but one was expected. The baseline is the alias table alone: what `ledger resolve` does
for KEV names.

## Review

Labels were drafted on 2026-11-15 from the evidence above and need the maintainer's review before
the gate box is ticked. To review: read `pairs.csv`, correct any label (with a reason in
`evidence`), run the test, and record the date and result in docs/ROADMAP.md.
