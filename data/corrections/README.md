# Corrections

`corrections.csv` holds every accepted correction request ([CORRECTIONS.md](../../CORRECTIONS.md)).
It is loaded into `silver.corrections` and applied before every gold build, so a correction
reaches the API, the site, and the downloads with the next daily run after it is deployed.
Changes go through a reviewed commit, like the seed data.

| Column | Meaning |
|---|---|
| `request_ref` | `github#<issue>` for a public request, `private#<case>` for an emailed one. Never the requester's name or address. |
| `target_id` | The record's ID, as in the downloads (`vulnerability--…`, `identity--…`, `incident--…`). |
| `action` | `suppress` removes the record and every row that refers to it (a vendor's products, an organization's incidents). `amend` sets one field. |
| `amend_field`, `amend_value` | For `amend` only: the field, and its new value as JSON (`"known"` with the quotes, `true`, `null`). In the CSV, a JSON string is written `"""known"""`. |
| `reason` | `inaccurate`, `outdated`, `misattributed`, `disputed`, `retracted`, or `out-of-policy`. |
| `decided_at` | When the request was decided, in UTC (`2026-10-28T12:00:00Z`). |
| `public_note` | Optional, shown in the public changelog. Must not repeat removed content. |

## Adding a correction

1. Add the row and run `uv run ledger corrections`. It validates the file and lists the table
   each target is in; a target that matches no record is reported as `NOT FOUND`.
2. Run `make check` (it validates the committed file), commit, and deploy.
3. Reply on the issue with the outcome.

The public changelog is the `corrections_log` download: each correction's record ID, action,
field, reason, date, and note, without amended values.

## What a removal reaches

- **Gold, the API, and downloads:** the record is gone from the next build. Gold tables keep no
  history (each build replaces them with their files), so it can't be reached through older
  snapshots either.
- **Bronze and silver:** keep the source data, so each decision can be audited. Neither is
  published.
- **Backups:** the nightly archives hold the earlier gold until they rotate out (7 by default).
- A removal because the source data itself is out of policy (for example, it names a person)
  also needs that data purged from bronze and silver by hand. No current source collects such
  data.
