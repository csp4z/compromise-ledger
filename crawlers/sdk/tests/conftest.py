import pytest
from ledger_crawl import CrawlerMeta, RateLimit


@pytest.fixture
def meta() -> CrawlerMeta:
    return CrawlerMeta(
        id="example",
        version="0.1.0",
        description="Test crawler",
        schedule="0 6 * * *",
        rate_limit=RateLimit(requests=1, per_seconds=2),
        license="CC0-1.0",
        allowed_hosts=("data.example.org",),
        content_types=("application/json",),
        max_bytes=1024,
    )
