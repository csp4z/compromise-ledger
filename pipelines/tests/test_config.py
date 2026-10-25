from pathlib import Path

import pytest
from ledger_pipelines.blobs import open_blob_store
from ledger_pipelines.config import DEFAULT_CONTACT, Settings


def test_lite_defaults(tmp_path: Path) -> None:
    s = Settings.from_env({"CL_DATA_DIR": str(tmp_path)})
    assert (s.profile, s.storage) == ("lite", "local")
    assert s.catalog_uri == f"sqlite:///{tmp_path.resolve() / 'catalog.db'}"
    assert s.warehouse == (tmp_path.resolve() / "warehouse").as_uri()
    assert s.crawler_contact == DEFAULT_CONTACT


def test_per_concern_override() -> None:
    s = Settings.from_env({"CL_PROFILE": "lite", "CL_STORAGE": "s3"})
    assert s.storage == "s3"
    with pytest.raises(NotImplementedError, match="S3"):
        open_blob_store(s)


@pytest.mark.parametrize(("var", "value"), [("CL_PROFILE", "huge"), ("CL_STORAGE", "ftp")])
def test_rejects_bad_values(var: str, value: str) -> None:
    with pytest.raises(ValueError, match=var):
        Settings.from_env({var: value})
