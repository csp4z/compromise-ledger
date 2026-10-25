"""Writes gold tables as Parquet, CSV, and JSON files with a checksummed ``datasets.json``."""

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq
from ledger_schemas import SCHEMA_VERSION

DATASET_LICENSE = "CC-BY-4.0"
ATTRIBUTION = (
    "Compromise Ledger (https://github.com/csp4z/compromise-ledger), CC BY 4.0. "
    "Preserve source attribution and status labels; upstream sources keep their own terms."
)
FORMATS = ("parquet", "csv", "json")


@dataclass(frozen=True, slots=True)
class ExportTable:
    name: str
    table: pa.Table
    snapshot_id: int | None


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    description: str
    license: str


def _json_default(value: object) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _write(path: Path, writer: Any) -> None:
    """Write via a temporary file and rename, so a reader never sees a partial file."""
    tmp = path.with_name(f".tmp-{path.name}")
    writer(tmp)
    os.replace(tmp, path)


def _write_format(table: pa.Table, fmt: str, path: Path) -> None:
    if fmt == "parquet":
        _write(path, lambda p: pq.write_table(table, p, compression="zstd"))
    elif fmt == "csv":
        _write(path, lambda p: pa_csv.write_csv(table, p))
    else:
        text = json.dumps(table.to_pylist(), default=_json_default, ensure_ascii=False, indent=1)
        _write(path, lambda p: p.write_text(text + "\n", encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export(
    tables: Sequence[ExportTable],
    sources: Sequence[Source],
    out_dir: Path,
    *,
    generated_at: datetime,
) -> dict[str, Any]:
    """Write every table in every format, then the manifest last, and return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for item in tables:
        for fmt in FORMATS:
            path = out_dir / f"{item.name}.{fmt}"
            _write_format(item.table, fmt, path)
            files.append(
                {
                    "path": path.name,
                    "table": f"gold.{item.name}",
                    "format": fmt,
                    "rows": item.table.num_rows,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "iceberg_snapshot_id": item.snapshot_id,
                }
            )
    manifest: dict[str, Any] = {
        "dataset": "compromise-ledger",
        "generated_at": generated_at.isoformat(),
        "schema_version": SCHEMA_VERSION,
        "license": DATASET_LICENSE,
        "attribution": ATTRIBUTION,
        "sources": [
            {"id": s.id, "description": s.description, "license": s.license} for s in sources
        ],
        "files": files,
    }
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    _write(out_dir / "datasets.json", lambda p: p.write_text(text, encoding="utf-8"))
    return manifest


def verify(out_dir: Path) -> list[str]:
    """Check every file listed in ``datasets.json``; return the problems found."""
    manifest: Mapping[str, Any] = json.loads((out_dir / "datasets.json").read_text("utf-8"))
    problems: list[str] = []
    for entry in manifest["files"]:
        path = out_dir / entry["path"]
        if not path.exists():
            problems.append(f"{entry['path']}: missing")
        elif sha256_file(path) != entry["sha256"]:
            problems.append(f"{entry['path']}: checksum mismatch")
    return problems
