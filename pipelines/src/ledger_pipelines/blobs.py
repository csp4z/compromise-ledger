"""Content-addressed blob storage for raw documents."""

import os
import tempfile
from pathlib import Path
from typing import Protocol

from ledger_pipelines.config import Settings


class BlobStore(Protocol):
    def put(self, key: str, data: bytes) -> None:
        """Store ``data`` under ``key``. Keys are content-addressed, so an existing key is kept."""
        ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


class LocalBlobStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"blob key escapes the store: {key!r}")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename, so a crash never leaves a partial blob under its final key.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


def open_blob_store(settings: Settings) -> BlobStore:
    if settings.storage == "local":
        return LocalBlobStore(settings.data_dir)
    # Deferred per the Phase 1a cut list until the public server needs it.
    raise NotImplementedError("S3 blob storage is not implemented yet; use CL_STORAGE=local")
