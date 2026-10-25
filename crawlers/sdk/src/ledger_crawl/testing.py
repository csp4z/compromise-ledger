"""Offline test helpers for plugin authors. Tests never touch the network."""

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ledger_crawl.context import CrawlContext
from ledger_crawl.meta import CrawlerMeta
from ledger_crawl.ratelimit import RateLimiter

FIXED_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class Fixture:
    """A recorded response."""

    def __init__(
        self, body: bytes | Path, *, content_type: str = "application/json", status: int = 200
    ) -> None:
        self.body = body.read_bytes() if isinstance(body, Path) else body
        self.content_type = content_type
        self.status = status


def fixture_transport(routes: Mapping[str, Fixture]) -> httpx.MockTransport:
    """Serve recorded responses by exact URL (query string included).

    robots.txt is answered with 404 (no restrictions) unless a route provides it. Any other
    unknown URL fails the test, so a crawler can't silently fetch something unexpected.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        fixture = routes.get(url)
        if fixture is None:
            if request.url.path == "/robots.txt":
                return httpx.Response(404)
            raise AssertionError(f"unexpected request: {url}")
        return httpx.Response(
            fixture.status, content=fixture.body, headers={"content-type": fixture.content_type}
        )

    return httpx.MockTransport(handler)


def offline_context(
    meta: CrawlerMeta,
    routes: Mapping[str, Fixture],
    *,
    last_success: datetime | None = None,
    now: datetime = FIXED_NOW,
) -> CrawlContext:
    """A context that serves fixtures, never sleeps, and has a fixed clock."""
    return CrawlContext(
        meta,
        contact="tests@example.invalid",
        last_success=last_success,
        transport=fixture_transport(routes),
        clock=lambda: now,
        limiter=RateLimiter(meta.rate_limit, clock=lambda: 0.0, sleep=lambda _: None),
    )
