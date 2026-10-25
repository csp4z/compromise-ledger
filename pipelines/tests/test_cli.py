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
