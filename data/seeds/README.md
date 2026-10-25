# Seed data

Curated reference data, changed through reviewed PRs and licensed
[CC BY 4.0](../../LICENSE-DATA) like the rest of the dataset. `ledger resolve` reads these files
to map the vendor names sources use to canonical vendors.

## `vendors.csv`

| Column | Meaning |
|---|---|
| `slug` | Canonical ID, lower-case and hyphenated. Part of every vendor and product ID, so it never changes once published. Renames go in `vendor_aliases.csv`. |
| `name` | Display name. Also matched against source names. |
| `is_security_vendor` | `true` or `false`, by the rule below. |
| `source` | Citation for a `true` (required): usually the vendor's own site, where it describes its business. |
| `note` | Primary business for security vendors; the reason for borderline `false` calls. |

### Who counts as a security vendor

A vendor counts if **security is its primary business**: what it is mainly known for and earns
most of its revenue from. A generalist with a security product line does not count, even a
large one. So Cisco (networking), Microsoft, and Juniper are `false`, while Fortinet, Palo Alto
Networks, and Sophos are `true`.

The rule is applied to the company the source names, at the time of the record. An acquired
security company keeps its own row (Pulse Secure is `true`, although Ivanti now owns it), and
its old products stay attributed to it.

Borderline `false` calls carry a note with the reason, so they can be revisited in review.
Current borderline cases: Ivanti, F5, Splunk, Acronis, Versa, and the networking vendors with
firewall lines (Cisco, Juniper, Zyxel). Fortra is `true` because it describes itself as a
cybersecurity company.

## `vendor_aliases.csv`

Other names for a vendor: `alias`, `vendor_slug`, `note`. Matching is exact after Unicode
normalization, case folding, and whitespace collapsing, so `QNAP Systems` needs an alias but
`qnap ` does not. Each name may map to only one vendor.

Some names are left unresolved on purpose. `D-Link and TRENDnet` names two vendors, and
`Npm package` names none. They appear in `ops.unresolved_vendor_names` with every other name that
doesn't match, which is published so the gaps are visible.

## Changing seeds

- Add a vendor when a source introduces a new name: check `ops.unresolved_vendor_names` after
  `ledger resolve`.
- Cite a source for every `true`, and give the reason for any borderline call.
- `make check` validates both files (`pipelines/tests/test_resolve.py`).
