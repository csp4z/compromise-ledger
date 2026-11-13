"""Loads ``data/seeds/third_party_incidents.csv``: SEC filings whose incident happened at a third
party (a vendor or service provider), not in systems the company runs. Kept by hand after reading
each filing; gold joins it to incidents by accession number."""

import csv
import hashlib
import io
from datetime import datetime
from pathlib import Path

from ledger_schemas import Provenance, ThirdPartyIncident
from pydantic import ValidationError

from ledger_pipelines import __version__

FILE_NAME = "third_party_incidents.csv"
COLUMNS = ["sec_accession", "third_party", "note"]
SOURCE_URL = f"https://github.com/csp4z/compromise-ledger/blob/main/data/seeds/{FILE_NAME}"
REVIEW_ID = "third-party-review"
# A maintainer's reading of the company's own filing.
REVIEW_CONFIDENCE = 90
LICENSE = "CC-BY-4.0"


class ThirdPartyFileError(ValueError):
    """The third-party file is malformed. The message names the line."""


def load_third_party(path: Path, *, loaded_at: datetime) -> list[ThirdPartyIncident]:
    """Read and validate the file. An empty ``third_party`` means the filing names no one."""
    data = path.read_bytes()
    reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
    if reader.fieldnames != COLUMNS:
        raise ThirdPartyFileError(
            f"{path.name}: expected columns {COLUMNS}, got {reader.fieldnames}"
        )
    provenance = Provenance(
        source_url=SOURCE_URL,
        raw_document_id=hashlib.sha256(data).hexdigest(),
        crawled_at=loaded_at,
        parser_id=REVIEW_ID,
        parser_version=__version__,
        confidence=REVIEW_CONFIDENCE,
        license=LICENSE,
    )
    marks: list[ThirdPartyIncident] = []
    seen: set[str] = set()
    for line, row in enumerate(reader, start=2):
        try:
            mark = ThirdPartyIncident.model_validate(
                {k: v for k, v in row.items() if v} | {"provenance": provenance}
            )
        except ValidationError as exc:
            raise ThirdPartyFileError(f"{path.name} line {line}: {exc}") from exc
        if mark.id in seen:
            raise ThirdPartyFileError(f"{path.name} line {line}: duplicate accession")
        seen.add(mark.id)
        marks.append(mark)
    return marks
