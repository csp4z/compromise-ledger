"""Minimum-interval rate limiter."""

import time
from collections.abc import Callable

from ledger_crawl.meta import RateLimit


class RateLimiter:
    def __init__(
        self,
        limit: RateLimit,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = limit.interval
        self._clock = clock
        self._sleep = sleep
        self._next: float | None = None

    def wait(self) -> None:
        """Block until the next request is allowed."""
        now = self._clock()
        if self._next is not None and now < self._next:
            self._sleep(self._next - now)
            now = self._next
        self._next = now + self._interval
