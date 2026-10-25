from ledger_crawl import RateLimit
from ledger_crawl.ratelimit import RateLimiter


def test_spaces_requests_by_interval() -> None:
    now = 100.0
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        nonlocal now
        slept.append(seconds)
        now += seconds

    limiter = RateLimiter(RateLimit(requests=5, per_seconds=30), clock=lambda: now, sleep=sleep)
    limiter.wait()
    limiter.wait()
    now += 2
    limiter.wait()
    assert slept == [6.0, 4.0]


def test_no_wait_after_long_gap() -> None:
    now = 0.0
    slept: list[float] = []
    limiter = RateLimiter(
        RateLimit(requests=1, per_seconds=1), clock=lambda: now, sleep=slept.append
    )
    limiter.wait()
    now = 10.0
    limiter.wait()
    assert slept == []
