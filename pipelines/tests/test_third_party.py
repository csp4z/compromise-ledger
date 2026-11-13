from datetime import UTC, datetime
from pathlib import Path

import pytest
from ledger_pipelines.third_party import FILE_NAME, ThirdPartyFileError, load_third_party

NOW = datetime(2026, 11, 13, tzinfo=UTC)
SEEDS = Path(__file__).resolve().parents[2] / "data" / "seeds"
HEADER = "sec_accession,third_party,note\n"


def test_the_committed_file_is_valid() -> None:
    marks = load_third_party(SEEDS / FILE_NAME, loaded_at=NOW)
    assert marks, "the list starts with the cases from the 8.01 hand check"
    assert all(
        m.provenance.source_url and m.provenance.source_url.endswith(FILE_NAME) for m in marks
    )


def test_an_empty_third_party_means_unnamed(tmp_path: Path) -> None:
    path = tmp_path / FILE_NAME
    path.write_text(HEADER + '0000000001-26-000001,,"A vendor\'s incident."\n', encoding="utf-8")
    (mark,) = load_third_party(path, loaded_at=NOW)
    assert mark.third_party is None
    assert mark.provenance.crawled_at == NOW


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("accession,note\n", "expected columns"),
        (HEADER + "not-an-accession,,note\n", "line 2"),
        (HEADER + "0000000001-26-000001,,\n", "line 2"),  # a note is required
        (HEADER + "0000000001-26-000001,,a\n0000000001-26-000001,,b\n", "duplicate"),
    ],
)
def test_malformed_files_name_the_line(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / FILE_NAME
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ThirdPartyFileError, match=message):
        load_third_party(path, loaded_at=NOW)
