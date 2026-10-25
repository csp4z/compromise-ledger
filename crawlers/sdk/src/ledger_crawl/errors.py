"""Errors raised by the crawl context. A crawler lets them propagate; the run then fails."""


class CrawlError(Exception):
    """Base class for crawl failures."""


class HostNotAllowedError(CrawlError):
    """A request or redirect targeted a host outside ``CrawlerMeta.allowed_hosts``."""


class RobotsDisallowedError(CrawlError):
    """robots.txt disallows the URL for this crawler."""


class ResponseTooLargeError(CrawlError):
    """The response body exceeded ``CrawlerMeta.max_bytes``."""


class UnexpectedContentTypeError(CrawlError):
    """The response's content type is not in ``CrawlerMeta.content_types``."""


class HttpStatusError(CrawlError):
    """The server answered with a non-2xx status."""

    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"HTTP {status} for {url}")
        self.url = url
        self.status = status
