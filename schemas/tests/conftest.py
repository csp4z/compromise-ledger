from datetime import UTC, datetime

import pytest
from ledger_schemas import Provenance


@pytest.fixture
def provenance() -> Provenance:
    return Provenance(
        source_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        raw_document_id="a" * 64,
        crawled_at=datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
        parser_id="cisa-kev",
        parser_version="0.1.0",
        confidence=90,
        license="CC0-1.0",
    )
