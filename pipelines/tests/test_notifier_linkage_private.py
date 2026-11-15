"""Measures notifier grouping on hand-labelled pairs of real breach-notice names.

The pairs name notifying organizations, which are not published (DATA_POLICY.md), so the file
is kept out of Git in ``.private/`` and this test is skipped where it is absent (CI). The
measurement of record is in ADR 0008.
"""

import csv
from pathlib import Path

import pytest
from ledger_pipelines.names import group_id

PAIRS = Path(__file__).parents[2] / ".private" / "notifier-pairs.csv"
MIN_PRECISION = 0.98


@pytest.mark.skipif(not PAIRS.exists(), reason="private labelled pairs are not in Git")
def test_core_name_grouping_is_precise_on_real_notifier_names() -> None:
    with PAIRS.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["same"] in ("0", "1")]
    predicted = [(r, group_id(r["name_a"]) == group_id(r["name_b"])) for r in rows]
    tp = sum(1 for r, same in predicted if same and r["same"] == "1")
    fp = sum(1 for r, same in predicted if same and r["same"] == "0")
    fn = sum(1 for r, same in predicted if not same and r["same"] == "1")
    assert len(rows) >= 100
    assert tp / (tp + fp) >= MIN_PRECISION
    assert tp / (tp + fn) >= 0.9
