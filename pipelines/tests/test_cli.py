from pathlib import Path

import pytest
from ledger_pipelines.cli import main


def test_sources_lists_installed_crawlers(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["sources"]) == 0
    assert "cisa-kev" in capsys.readouterr().out


def test_unknown_source_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CL_DATA_DIR", str(tmp_path))
    assert main(["crawl", "nope"]) == 2
    assert "no clearnet crawler named 'nope'" in capsys.readouterr().err


def test_corrections_reports_targets_that_match_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    corrections = tmp_path / "corrections.csv"
    corrections.write_text(
        "request_ref,target_id,action,amend_field,amend_value,reason,decided_at,public_note\n"
        "github#3,identity--00000000-0000-5000-8000-000000000000,suppress,,,inaccurate,"
        "2026-10-28T12:00:00Z,\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CL_DATA_DIR", str(tmp_path / "lake"))
    monkeypatch.setenv("CL_CORRECTIONS_FILE", str(corrections))
    assert main(["corrections"]) == 1
    captured = capsys.readouterr()
    assert "NOT FOUND" in captured.out
    assert "1 with no matching record" in captured.err
    corrections.write_text("bad\n", encoding="utf-8")
    assert main(["corrections"]) == 2
