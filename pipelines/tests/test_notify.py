import json
from pathlib import Path

import httpx
from ledger_pipelines.checks import Problem
from ledger_pipelines.config import Settings
from ledger_pipelines.notify import alert

PROBLEMS = [Problem("cisa-kev", "crawl-failed", "HTTP 503")]


def settings(tmp_path: Path, **env: str) -> Settings:
    return Settings.from_env({"CL_DATA_DIR": str(tmp_path), **env})


def recorder(responses: dict[tuple[str, str], httpx.Response]):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        key = (request.method, f"{request.url.host}{request.url.path}")
        return responses.get(key, httpx.Response(200, json={}))

    return seen, httpx.MockTransport(handler)


def test_nothing_configured_sends_nothing(tmp_path: Path) -> None:
    seen, transport = recorder({})
    assert alert(settings(tmp_path), PROBLEMS, transport=transport) == []
    assert seen == []


def test_secrets_stay_out_of_repr(tmp_path: Path) -> None:
    s = settings(tmp_path, CL_GITHUB_TOKEN="ghp_secret", CL_NTFY_URL="https://ntfy.sh/topic")
    assert "ghp_secret" not in repr(s) and "topic" not in repr(s)


def test_ntfy_and_healthchecks(tmp_path: Path) -> None:
    seen, transport = recorder({})
    s = settings(
        tmp_path, CL_NTFY_URL="https://ntfy.sh/t", CL_HEALTHCHECKS_URL="https://hc-ping.com/u"
    )
    alert(s, PROBLEMS, transport=transport)
    assert [(r.method, str(r.url)) for r in seen] == [
        ("POST", "https://ntfy.sh/t"),
        ("GET", "https://hc-ping.com/u/fail"),
    ]
    assert b"cisa-kev: crawl-failed: HTTP 503" in seen[0].content

    seen.clear()
    alert(s, [], transport=transport)  # healthy: only the dead-man's-switch ping
    assert [(r.method, str(r.url)) for r in seen] == [("GET", "https://hc-ping.com/u")]


def test_github_opens_an_issue_then_comments(tmp_path: Path) -> None:
    s = settings(tmp_path, CL_GITHUB_TOKEN="t", CL_GITHUB_REPO="o/r")
    issues = ("GET", "api.github.com/repos/o/r/issues")

    seen, transport = recorder({issues: httpx.Response(200, json=[])})
    alert(s, PROBLEMS, transport=transport)
    created = seen[-1]
    assert (created.method, created.url.path) == ("POST", "/repos/o/r/issues")
    payload = json.loads(created.content)
    assert payload["labels"] == ["crawler-broken"] and "cisa-kev" in payload["title"]
    assert created.headers["authorization"] == "Bearer t"

    seen, transport = recorder({issues: httpx.Response(200, json=[{"number": 7}])})
    alert(s, PROBLEMS, transport=transport)
    assert (seen[-1].method, seen[-1].url.path) == ("POST", "/repos/o/r/issues/7/comments")


def test_delivery_errors_are_returned_not_raised(tmp_path: Path) -> None:
    _, transport = recorder({("POST", "ntfy.sh/t"): httpx.Response(500)})
    errors = alert(
        settings(tmp_path, CL_NTFY_URL="https://ntfy.sh/t"), PROBLEMS, transport=transport
    )
    assert len(errors) == 1 and errors[0].startswith("ntfy:")
