from pathlib import Path

import pytest
from ledger_pipelines.corrections import COLUMNS, CorrectionsFileError, load_corrections
from ledger_schemas import make_id

REPO_FILE = Path(__file__).parents[2] / "data" / "corrections" / "corrections.csv"
HEADER = ",".join(COLUMNS) + "\n"
TARGET = make_id("vulnerability", "CVE-2024-3400")


def write(tmp_path: Path, rows: str) -> Path:
    path = tmp_path / "corrections.csv"
    path.write_text(HEADER + rows, encoding="utf-8")
    return path


def test_loads_suppress_and_amend(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        f"github#1,{TARGET},suppress,,,inaccurate,2026-10-28T12:00:00Z,\n"
        f'private#a1,{TARGET},amend,kev_ransomware_use,"""known""",outdated,2026-10-29T09:00:00Z,'
        "CISA updated the flag\n",
    )
    suppress, amend = load_corrections(path)
    assert (suppress.action, suppress.amend_field, suppress.public_note) == ("suppress", None, None)
    assert (amend.amend_field, amend.amend_value) == ("kev_ransomware_use", '"known"')


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (f"github#1,{TARGET},remove,,,inaccurate,2026-10-28T12:00:00Z,\n", "line 2"),
        (f"github#1,{TARGET},amend,,,inaccurate,2026-10-28T12:00:00Z,\n", "amend_field"),
        (f"github#1,{TARGET},amend,f,not-json,inaccurate,2026-10-28T12:00:00Z,\n", "line 2"),
        (f"someone,{TARGET},suppress,,,inaccurate,2026-10-28T12:00:00Z,\n", "line 2"),
        (f"github#1,{TARGET},suppress,,,inaccurate,2026-10-28,\n", "line 2"),
        (f"github#1,{TARGET},suppress,,,inaccurate,2026-10-28T12:00:00Z,\n" * 2, "duplicate"),
    ],
)
def test_rejects_bad_rows(tmp_path: Path, rows: str, message: str) -> None:
    with pytest.raises(CorrectionsFileError, match=message):
        load_corrections(write(tmp_path, rows))


def test_rejects_wrong_columns(tmp_path: Path) -> None:
    path = tmp_path / "corrections.csv"
    path.write_text("request_ref,target_id\n", encoding="utf-8")
    with pytest.raises(CorrectionsFileError, match="expected columns"):
        load_corrections(path)


def test_committed_file_is_valid() -> None:
    load_corrections(REPO_FILE)
