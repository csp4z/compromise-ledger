from pathlib import Path

import pytest
from ledger_pipelines.cli import EXIT_LOCKED, main
from ledger_pipelines.lock import LockedError, exclusive


def test_second_holder_is_refused_until_release(tmp_path: Path) -> None:
    with exclusive(tmp_path):
        assert (tmp_path / "ledger.lock").read_text().strip().isdigit()
        with pytest.raises(LockedError, match="in progress"), exclusive(tmp_path):
            pass
    with exclusive(tmp_path):  # released: can be taken again
        pass


def test_cli_exits_75_while_another_run_holds_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CL_DATA_DIR", str(tmp_path))
    with exclusive(tmp_path):
        assert main(["resolve"]) == EXIT_LOCKED
    assert "another ledger run is in progress" in capsys.readouterr().err


def test_check_does_not_need_the_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CL_DATA_DIR", str(tmp_path))
    with exclusive(tmp_path):
        assert main(["check"]) != EXIT_LOCKED
