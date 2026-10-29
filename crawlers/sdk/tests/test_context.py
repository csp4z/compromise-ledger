import hashlib
from collections.abc import Iterator

import httpx
import pytest
from ledger_crawl import CrawlContext, CrawlerMeta
from ledger_crawl.errors import (
    HostNotAllowedError,
    HttpStatusError,
    ResponseTooLargeError,
    RobotsDisallowedError,
    UnexpectedContentTypeError,
)
from ledger_crawl.ratelimit import RateLimiter
from ledger_crawl.testing import FIXED_NOW, Fixture, offline_context

URL = "https://data.example.org/feed.json"


def context_with(meta: CrawlerMeta, handler: httpx.MockTransport) -> CrawlContext:
    return CrawlContext(
        meta,
        contact="tests@example.invalid",
        transport=handler,
        limiter=RateLimiter(meta.rate_limit, clock=lambda: 0.0, sleep=lambda _: None),
    )


def test_fetch_builds_content_addressed_raw_document(meta: CrawlerMeta) -> None:
    body = b'{"ok": true}'
    routes = {URL: Fixture(body, content_type="application/json; charset=utf-8")}
    with offline_context(meta, routes) as ctx:
        doc = ctx.get(URL)
    assert doc.body == body
    assert doc.raw.id == hashlib.sha256(body).hexdigest()
    assert doc.raw.source_id == "example"
    assert doc.raw.content_type == "application/json"
    assert doc.raw.fetched_at == FIXED_NOW
    assert doc.raw.size_bytes == len(body)


def test_query_params_are_part_of_the_url(meta: CrawlerMeta) -> None:
    routes = {f"{URL}?page=2": Fixture(b"{}")}
    with offline_context(meta, routes) as ctx:
        assert ctx.get(URL, params={"page": 2}).raw.url == f"{URL}?page=2"


def test_sends_user_agent_with_contact(meta: CrawlerMeta) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["user-agent"])
        status = 404 if request.url.path == "/robots.txt" else 200
        return httpx.Response(status, content=b"{}", headers={"content-type": "application/json"})

    with context_with(meta, httpx.MockTransport(handler)) as ctx:
        ctx.get(URL)
    assert seen[-1].startswith("compromise-ledger/")
    assert "tests@example.invalid" in seen[-1]


def test_name_email_user_agent(meta: CrawlerMeta) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["user-agent"])
        status = 404 if request.url.path == "/robots.txt" else 200
        return httpx.Response(status, content=b"{}", headers={"content-type": "application/json"})

    sec_style = meta.model_copy(update={"user_agent": "name-email"})
    with context_with(sec_style, httpx.MockTransport(handler)) as ctx:
        ctx.get(URL)
    assert seen[-1] == "Compromise Ledger tests@example.invalid"


def test_contact_is_required(meta: CrawlerMeta) -> None:
    with pytest.raises(ValueError, match="contact"):
        CrawlContext(meta, contact=" ")


@pytest.mark.parametrize(
    "url", ["https://evil.example.com/x.json", "http://data.example.org/feed.json"]
)
def test_rejects_hosts_and_schemes_off_the_allowlist(meta: CrawlerMeta, url: str) -> None:
    with offline_context(meta, {}) as ctx, pytest.raises(HostNotAllowedError):
        ctx.get(url)


def test_rejects_redirect_off_the_allowlist(meta: CrawlerMeta) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.host == "data.example.org":
            return httpx.Response(302, headers={"location": "https://files.example.net/dump.zip"})
        raise AssertionError("followed a redirect off the allowlist")

    with (
        context_with(meta, httpx.MockTransport(handler)) as ctx,
        pytest.raises(HostNotAllowedError),
    ):
        ctx.get(URL)


def test_honors_robots_txt(meta: CrawlerMeta) -> None:
    robots = Fixture(b"User-agent: *\nDisallow: /feed", content_type="text/plain")
    routes = {"https://data.example.org/robots.txt": robots, URL: Fixture(b"{}")}
    with offline_context(meta, routes) as ctx, pytest.raises(RobotsDisallowedError):
        ctx.get(URL)


def test_robots_server_error_means_disallow(meta: CrawlerMeta) -> None:
    routes = {
        "https://data.example.org/robots.txt": Fixture(b"", status=503),
        URL: Fixture(b"{}"),
    }
    with offline_context(meta, routes) as ctx, pytest.raises(RobotsDisallowedError, match="503"):
        ctx.get(URL)


def test_robots_fetched_once_per_host(meta: CrawlerMeta) -> None:
    robots_hits = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal robots_hits
        if request.url.path == "/robots.txt":
            robots_hits += 1
            return httpx.Response(404)
        return httpx.Response(200, content=b"{}", headers={"content-type": "application/json"})

    with context_with(meta, httpx.MockTransport(handler)) as ctx:
        ctx.get(URL)
        ctx.get(URL)
    assert robots_hits == 1


def test_rejects_unexpected_content_type(meta: CrawlerMeta) -> None:
    routes = {URL: Fixture(b"PK\x03\x04", content_type="application/zip")}
    with offline_context(meta, routes) as ctx, pytest.raises(UnexpectedContentTypeError):
        ctx.get(URL)


def test_rejects_oversized_body(meta: CrawlerMeta) -> None:
    routes = {URL: Fixture(b"x" * (meta.max_bytes + 1))}
    with offline_context(meta, routes) as ctx, pytest.raises(ResponseTooLargeError):
        ctx.get(URL)


def test_rejects_oversized_stream_without_content_length(meta: CrawlerMeta) -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(4):
            yield b"x" * 512

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=chunks(), headers={"content-type": "application/json"})

    with (
        context_with(meta, httpx.MockTransport(handler)) as ctx,
        pytest.raises(ResponseTooLargeError),
    ):
        ctx.get(URL)


def test_non_success_status_raises(meta: CrawlerMeta) -> None:
    routes = {URL: Fixture(b"{}", status=503)}
    with offline_context(meta, routes) as ctx, pytest.raises(HttpStatusError) as err:
        ctx.get(URL)
    assert err.value.status == 503


def test_unknown_url_fails_loudly_in_tests(meta: CrawlerMeta) -> None:
    with offline_context(meta, {}) as ctx, pytest.raises(AssertionError, match="unexpected"):
        ctx.get(URL)


def flaky(failures: list[httpx.Response | Exception]) -> tuple[list[int], httpx.MockTransport]:
    """Fail with each item in turn, then succeed. Returns the call count and transport."""
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls.append(1)
        if failures:
            failure = failures.pop(0)
            if isinstance(failure, Exception):
                raise failure
            return failure
        return httpx.Response(200, content=b"{}", headers={"content-type": "application/json"})

    return calls, httpx.MockTransport(handler)


def retrying_context(
    meta: CrawlerMeta, transport: httpx.MockTransport, slept: list[float]
) -> CrawlContext:
    return CrawlContext(
        meta,
        contact="tests@example.invalid",
        transport=transport,
        limiter=RateLimiter(meta.rate_limit, clock=lambda: 0.0, sleep=lambda _: None),
        sleep=slept.append,
    )


def test_retries_transient_failures_with_backoff(meta: CrawlerMeta) -> None:
    calls, transport = flaky(
        [httpx.Response(503), httpx.RemoteProtocolError("peer closed connection")]
    )
    slept: list[float] = []
    with retrying_context(meta.model_copy(update={"retries": 3}), transport, slept) as ctx:
        assert ctx.get(URL).body == b"{}"
    assert len(calls) == 3
    assert slept == [10.0, 20.0]


def test_gives_up_after_the_last_retry(meta: CrawlerMeta) -> None:
    calls, transport = flaky([httpx.Response(503)] * 5)
    slept: list[float] = []
    ctx = retrying_context(meta.model_copy(update={"retries": 2}), transport, slept)
    with ctx, pytest.raises(HttpStatusError):
        ctx.get(URL)
    assert len(calls) == 3


@pytest.mark.parametrize("retries", [0, 3])
def test_does_not_retry_client_errors_or_when_not_opted_in(meta: CrawlerMeta, retries: int) -> None:
    status = 404 if retries else 503
    calls, transport = flaky([httpx.Response(status)])
    slept: list[float] = []
    ctx = retrying_context(meta.model_copy(update={"retries": retries}), transport, slept)
    with ctx, pytest.raises(HttpStatusError):
        ctx.get(URL)
    assert len(calls) == 1 and slept == []


def test_never_retries_policy_failures(meta: CrawlerMeta) -> None:
    zip_response = httpx.Response(200, content=b"PK", headers={"content-type": "application/zip"})
    calls, transport = flaky([zip_response])
    slept: list[float] = []
    ctx = retrying_context(meta.model_copy(update={"retries": 3}), transport, slept)
    with ctx, pytest.raises(UnexpectedContentTypeError):
        ctx.get(URL)
    assert len(calls) == 1
