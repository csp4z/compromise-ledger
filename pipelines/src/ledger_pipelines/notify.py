"""Alerts for failed health checks, and the scheduler's dead-man's switch.

Every channel is optional and configured by environment variables (see docs/DEVELOPMENT.md).
A failed alert is reported but never hides the original failure.
"""

import sys
from collections.abc import Sequence

import httpx

from ledger_pipelines.checks import Problem
from ledger_pipelines.config import Settings

ISSUE_LABEL = "crawler-broken"
GITHUB_API = "https://api.github.com"
TIMEOUT = httpx.Timeout(15.0)


def _summary(problems: Sequence[Problem]) -> str:
    return "\n".join(f"- {p}" for p in problems)


def notify_ntfy(client: httpx.Client, url: str, problems: Sequence[Problem]) -> None:
    client.post(
        url,
        content=_summary(problems).encode(),
        headers={
            "Title": "Compromise Ledger health check failed",
            "Priority": "high",
            "Tags": "warning",
        },
    ).raise_for_status()


def notify_github(client: httpx.Client, token: str, repo: str, problems: Sequence[Problem]) -> None:
    """Open a ``crawler-broken`` issue, or comment on the open one so failures don't pile up."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = f"`ledger check` found:\n\n{_summary(problems)}"
    existing = client.get(
        f"{GITHUB_API}/repos/{repo}/issues",
        params={"labels": ISSUE_LABEL, "state": "open", "per_page": 1},
        headers=headers,
    )
    existing.raise_for_status()
    issues = existing.json()
    if issues:
        url = f"{GITHUB_API}/repos/{repo}/issues/{issues[0]['number']}/comments"
        client.post(url, json={"body": body}, headers=headers).raise_for_status()
        return
    sources = sorted({p.source_id for p in problems})
    client.post(
        f"{GITHUB_API}/repos/{repo}/issues",
        json={
            "title": f"Health check failed: {', '.join(sources)}",
            "body": body,
            "labels": [ISSUE_LABEL],
        },
        headers=headers,
    ).raise_for_status()


def ping_healthchecks(client: httpx.Client, url: str, *, ok: bool) -> None:
    client.get(url if ok else f"{url.rstrip('/')}/fail").raise_for_status()


def alert(
    settings: Settings, problems: Sequence[Problem], *, transport: httpx.BaseTransport | None = None
) -> list[str]:
    """Send ``problems`` to every configured channel; return delivery errors."""
    errors: list[str] = []
    with httpx.Client(transport=transport, timeout=TIMEOUT) as client:
        if problems and settings.ntfy_url:
            try:
                notify_ntfy(client, settings.ntfy_url, problems)
            except httpx.HTTPError as exc:
                errors.append(f"ntfy: {exc}")
        if problems and settings.github_token:
            try:
                notify_github(client, settings.github_token, settings.github_repo, problems)
            except httpx.HTTPError as exc:
                errors.append(f"github: {exc}")
        if settings.healthchecks_url:
            try:
                ping_healthchecks(client, settings.healthchecks_url, ok=not problems)
            except httpx.HTTPError as exc:
                errors.append(f"healthchecks: {exc}")
    for error in errors:
        print(f"ledger: alert not delivered: {error}", file=sys.stderr)
    return errors
