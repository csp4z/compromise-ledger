"""robots.txt checks, following RFC 9309 for unreachable files."""

from urllib.robotparser import RobotFileParser

import httpx

from ledger_crawl.errors import CrawlError

ROBOTS_MAX_BYTES = 500 * 1024  # RFC 9309 §2.5: parse at least 500 KiB

_ALLOW_ALL: list[str] = []
_DISALLOW_ALL = ["User-agent: *", "Disallow: /"]


class RobotsPolicy:
    """Caches one robots.txt per scheme and host for the life of a crawl."""

    def __init__(self, client: httpx.Client, product_token: str) -> None:
        self._client = client
        self._token = product_token
        self._cache: dict[str, RobotFileParser] = {}
        self._reasons: dict[str, str] = {}

    @staticmethod
    def _origin(url: str) -> str:
        parsed = httpx.URL(url)
        return f"{parsed.scheme}://{parsed.netloc.decode('ascii')}"

    def allowed(self, url: str) -> bool:
        origin = self._origin(url)
        if origin not in self._cache:
            self._cache[origin] = self._load(origin, f"{origin}/robots.txt")
        return self._cache[origin].can_fetch(self._token, url)

    def reason(self, url: str) -> str:
        """Why ``url`` is disallowed, for error messages."""
        return self._reasons.get(self._origin(url), "disallowed by robots.txt")

    def _load(self, origin: str, robots_url: str) -> RobotFileParser:
        parser = RobotFileParser()
        try:
            response = self._client.get(robots_url)
        except (httpx.HTTPError, CrawlError) as exc:
            # Unreachable, or redirected off the allowlist: assume complete disallow (§2.3.1.4).
            self._reasons[origin] = f"robots.txt unreachable ({type(exc).__name__}: {exc})"
            lines = _DISALLOW_ALL
        else:
            if response.status_code >= 500:
                self._reasons[origin] = f"robots.txt returned HTTP {response.status_code}"
                lines = _DISALLOW_ALL
            elif response.status_code >= 400:
                lines = _ALLOW_ALL  # "Unavailable": no restrictions (§2.3.1.3)
            else:
                text = response.content[:ROBOTS_MAX_BYTES].decode("utf-8", errors="replace")
                lines = text.splitlines()
        parser.parse(lines)  # also marks the parser as read, which can_fetch() requires
        return parser
