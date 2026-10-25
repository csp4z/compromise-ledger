from pathlib import Path

import pytest
from ledger_pipelines.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings.from_env({"CL_DATA_DIR": str(tmp_path / "lake")})
