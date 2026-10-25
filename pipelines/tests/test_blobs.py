from pathlib import Path

import pytest
from ledger_pipelines.blobs import LocalBlobStore


def test_put_get_and_keep_existing(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)
    store.put("raw/x/ab/abc", b"first")
    store.put("raw/x/ab/abc", b"second")  # content-addressed: never overwritten
    assert store.get("raw/x/ab/abc") == b"first"
    assert store.exists("raw/x/ab/abc")
    assert not list(tmp_path.rglob(".tmp-*"))


def test_rejects_keys_outside_the_store(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        LocalBlobStore(tmp_path / "store").put("../outside", b"x")
