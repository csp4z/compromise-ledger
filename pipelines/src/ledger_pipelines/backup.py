"""Consistent local backups of the lakehouse (``ledger backup``).

The archive holds what can't be rebuilt: the SQLite catalog, the Iceberg warehouse, and the raw
blobs. Exports are left out; they are rebuilt from gold. Iceberg metadata stores absolute file
paths, so restore into the same ``CL_DATA_DIR`` path the backup was taken from.
"""

import re
import sqlite3
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from ledger_pipelines.config import Settings

ARCHIVE_RE = re.compile(r"^ledger-\d{8}T\d{6}Z\.tar\.gz$")
INCLUDED = ("warehouse", "raw")


def catalog_path(settings: Settings) -> Path:
    prefix = "sqlite:///"
    if not settings.catalog_uri.startswith(prefix):
        raise ValueError(f"backup supports SQLite catalogs only, not {settings.catalog_uri!r}")
    return Path(settings.catalog_uri.removeprefix(prefix))


def backup(settings: Settings, dest: Path, *, now: datetime, keep: int = 7) -> Path:
    """Write ``dest/ledger-<UTC time>.tar.gz`` and delete all but the newest ``keep`` archives.

    The caller holds the ledger lock, so no run writes while the archive is made.
    """
    if keep < 1:
        raise ValueError("keep at least one backup")
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / f"ledger-{now:%Y%m%dT%H%M%SZ}.tar.gz"
    partial = archive.with_name(f".partial-{archive.name}")
    with tempfile.TemporaryDirectory() as tmp:
        # SQLite's online backup API copies a consistent snapshot, unlike a plain file copy.
        snapshot = Path(tmp) / "catalog.db"
        with sqlite3.connect(catalog_path(settings)) as source, sqlite3.connect(snapshot) as copy:
            source.backup(copy)
        with tarfile.open(partial, "w:gz") as tar:
            tar.add(snapshot, arcname="catalog.db")
            for name in INCLUDED:
                if (settings.data_dir / name).exists():
                    tar.add(settings.data_dir / name, arcname=name)
    partial.rename(archive)
    archives = sorted(p for p in dest.iterdir() if ARCHIVE_RE.match(p.name))
    for old in archives[:-keep]:
        old.unlink()
    return archive
