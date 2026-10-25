"""The crawl context: the only way a crawler touches the network."""

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version

import httpx
from ledger_schemas import RawDocument

from ledger_crawl.errors import (
    HostNotAllowedError,
    HttpStatusError,
    ResponseTooLargeError,
    RobotsDisallowedError,
    UnexpectedContentTypeError,
)
from ledger_crawl.meta import CrawlerMeta
from ledger_crawl.ratelimit import RateLimiter
from ledger_crawl.robots import RobotsPolicy

UA_PRODUCT = "compromise-ledger"
PROJECT_URL = "https://github.com/csp4z/compromise-ledger"
MAX_REDIRECTS = 5


@dataclass(frozen=True, slots=True)
class FetchedDocument:
    """A fetched body and its bronze row. The runner stores both."""

    raw: RawDocument
    body: bytes


def user_agent(contact: str) -> str:
    return f"{UA_PRODUCT}/{version('ledger-crawl')} (+{PROJECT_URL}; {contact})"


class CrawlContext:
    """Enforces crawler etiquette and the data policy on every request.

    Requests are rate limited, checked against robots.txt and the host allowlist (redirects
    included), size-capped while streaming, and restricted to the declared content types. The
    returned :class:`FetchedDocument` is content-addressed, so crawlers never construct IDs.
    """

    def __init__(
        self,
        meta: CrawlerMeta,
        *,
        contact: str,
        last_success: datetime | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        limiter: RateLimiter | None = None,
    ) -> None:
        if not contact.strip():
            raise ValueError("a contact address is required for the User-Agent")
        self.meta = meta
        self.last_success = last_success
        """End of the previous successful run, for incremental crawls (None on the first run)."""
        self._clock = clock
        self._limiter = limiter or RateLimiter(meta.rate_limit)
        self._client = httpx.Client(
            transport=transport,
            headers={"User-Agent": user_agent(contact)},
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            timeout=httpx.Timeout(30.0, connect=10.0),
            event_hooks={"request": [self._check_host]},
        )
        self._robots = RobotsPolicy(self._client, UA_PRODUCT)

    def __enter__(self) -> "CrawlContext":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def now(self) -> datetime:
        return self._clock()

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> FetchedDocument:
        request_url = str(httpx.URL(url, params=params))
        self._check_host_of(request_url)
        if not self._robots.allowed(request_url):
            raise RobotsDisallowedError(request_url)
        self._limiter.wait()
        fetched_at = self.now()
        with self._client.stream("GET", request_url, headers=headers) as response:
            if not response.is_success:
                raise HttpStatusError(request_url, response.status_code)
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type not in self.meta.content_types:
                raise UnexpectedContentTypeError(f"{content_type!r} from {request_url}")
            body = self._read_capped(response)
            final_url = str(response.url)
            status = response.status_code
        raw = RawDocument(
            id=hashlib.sha256(body).hexdigest(),
            source_id=self.meta.id,
            crawler_version=self.meta.version,
            url=final_url,
            fetched_at=fetched_at,
            http_status=status,
            content_type=content_type,
            size_bytes=len(body),
        )
        return FetchedDocument(raw=raw, body=body)

    def _read_capped(self, response: httpx.Response) -> bytes:
        declared = response.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.meta.max_bytes:
            raise ResponseTooLargeError(f"{declared} bytes from {response.url}")
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > self.meta.max_bytes:
                raise ResponseTooLargeError(f"more than {self.meta.max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)

    def _check_host(self, request: httpx.Request) -> None:
        self._check_host_of(str(request.url))

    def _check_host_of(self, url: str) -> None:
        parsed = httpx.URL(url)
        if parsed.scheme != "https" or parsed.host not in self.meta.allowed_hosts:
            raise HostNotAllowedError(url)
