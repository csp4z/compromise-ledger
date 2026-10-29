"""Generate the committed JSON Schema files: ``python -m ledger_schemas.jsonschema [OUT_DIR]``."""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ledger_schemas import (
    SCHEMA_VERSION,
    Correction,
    CrawlRun,
    CveCount,
    Incident,
    Organization,
    Product,
    ProductMention,
    Provenance,
    RawDocument,
    Relationship,
    UnresolvedVendorName,
    Vendor,
    Vulnerability,
)

MODELS: dict[str, type[BaseModel]] = {
    "raw_document": RawDocument,
    "provenance": Provenance,
    "vendor": Vendor,
    "product": Product,
    "vulnerability": Vulnerability,
    "relationship": Relationship,
    "product_mention": ProductMention,
    "correction": Correction,
    "crawl_run": CrawlRun,
    "unresolved_vendor_name": UnresolvedVendorName,
    "cve_count": CveCount,
    "organization": Organization,
    "incident": Incident,
}

DEFAULT_OUT_DIR = Path(__file__).resolve().parents[2] / "json"


def render(model: type[BaseModel]) -> str:
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-ledger-schema-version": SCHEMA_VERSION,
        **model.model_json_schema(),
    }
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_all(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        (out_dir / f"{name}.schema.json").write_text(render(model), encoding="utf-8")


if __name__ == "__main__":
    write_all(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT_DIR)
