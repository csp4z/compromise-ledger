"""Applies ``silver.corrections`` to silver tables before anything is built from them."""

import json
from collections.abc import Mapping, Sequence
from typing import Any

import pyarrow as pa
from ledger_schemas import Correction

from ledger_pipelines.lakehouse import TABLES


def _suppressed_ids(tables: Mapping[str, pa.Table], corrections: Sequence[Correction]) -> set[str]:
    """Targets of suppressions, plus what depends on them: a vendor's products."""
    ids = {c.target_id for c in corrections if c.action == "suppress"}
    products = tables.get("silver.products")
    if products is not None and ids:
        for row in products.select(["id", "vendor_id"]).to_pylist():
            if row["vendor_id"] in ids:
                ids.add(row["id"])
    return ids


def _keep(name: str, row: Mapping[str, Any], suppressed: set[str]) -> bool:
    refs = [row.get("id"), row.get("vulnerability_id"), row.get("vendor_id")]
    if name == "silver.relationships":
        refs += [row["source_ref"], row["target_ref"]]
    return not any(ref in suppressed for ref in refs if ref is not None)


def apply_corrections(
    tables: Mapping[str, pa.Table], corrections: Sequence[Correction]
) -> dict[str, pa.Table]:
    """Return corrected copies of ``tables``.

    ``suppress`` removes the target and every row that refers to it. ``amend`` sets one field
    on every row with the target's ID; the row is re-validated, so an amend can't change a
    natural key (that is a suppression plus a new record) or break the schema.
    """
    suppressed = _suppressed_ids(tables, corrections)
    amends = sorted((c for c in corrections if c.action == "amend"), key=lambda c: c.decided_at)
    corrected: dict[str, pa.Table] = {}
    for name, table in tables.items():
        if not suppressed and not amends:
            corrected[name] = table
            continue
        model = TABLES[name]
        rows = [r for r in table.to_pylist() if _keep(name, r, suppressed)]
        for amend in amends:
            field, value = amend.amend_field, amend.amend_value
            if field is None or value is None:  # guaranteed by the model; narrows the types
                raise ValueError(f"{amend.id}: amend without a field and value")
            for i, row in enumerate(rows):
                if row.get("id") == amend.target_id:
                    if field not in row:
                        raise ValueError(f"{amend.id}: {name} has no field {field!r}")
                    updated = {**row, field: json.loads(value)}
                    rows[i] = model.model_validate(updated).model_dump()
        corrected[name] = pa.Table.from_pylist(rows, schema=table.schema)
    return corrected
