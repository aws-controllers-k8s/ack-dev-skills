"""GitHub client wrapper used by every ack-* maintainer skill.

Provides:
  - get_client(): authenticated PyGithub Github instance, with pre-flight
    OAuth-scope check that fails fast if the token can't do what the skills
    need.
  - graphql(): httpx-based GraphQL helper for batched fetches.
  - list_org_repos(): paginated, archived-aware repo discovery.
  - retry_on_rate_limit(): decorator for REST calls (PyGithub has its own
    pagination but no smart backoff for secondary rate limits).
  - bounded_map(): small ThreadPoolExecutor helper for per-repo fan-out.

Every script imports from here via the sys.path shim documented in
references/dry-run-conventions.md.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable, Iterator, TypeVar

import httpx
from github import Auth, Github
from github.GithubException import GithubException, RateLimitExceededException

REQUIRED_SCOPES = ("repo", "read:org")
GRAPHQL_URL = "https://api.github.com/graphql"
DEFAULT_WORKERS = 4
MAX_BACKOFF_SECONDS = 60

T = TypeVar("T")
R = TypeVar("R")


class AuthError(RuntimeError):
    """Auth/scope failure. Scripts catch this and exit 3."""


def _resolve_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    gh = shutil.which("gh")
    if gh:
        try:
            out = subprocess.run(
                [gh, "auth", "token"], capture_output=True, text=True, check=True
            )
            t = out.stdout.strip()
            if t:
                return t
        except subprocess.CalledProcessError:
            pass
    raise AuthError(
        "No GitHub token found. Set GITHUB_TOKEN or run `gh auth login`. "
        "See references/github-auth.md."
    )


def _check_scopes(token: str) -> None:
    """Hit /user and inspect X-OAuth-Scopes. Fail fast on missing scopes.

    Fine-grained PATs don't return X-OAuth-Scopes; in that case we trust the
    token and let the first real call fail with a precise error.
    """
    resp = httpx.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=10.0,
    )
    if resp.status_code == 401:
        raise AuthError(
            "GitHub returned 401. Token is invalid or expired. "
            "See references/github-auth.md."
        )
    if resp.status_code >= 400:
        raise AuthError(
            f"GitHub returned {resp.status_code} on /user: {resp.text[:200]}"
        )
    scopes_header = resp.headers.get("X-OAuth-Scopes")
    if scopes_header is None:
        return
    scopes = {s.strip() for s in scopes_header.split(",") if s.strip()}
    missing = [s for s in REQUIRED_SCOPES if s not in scopes]
    if missing:
        raise AuthError(
            f"Token is missing required scopes: {', '.join(missing)}. "
            f"Has: {sorted(scopes) or '(none)'}. "
            "Re-run `gh auth login -s repo,read:org` or update your PAT. "
            "See references/github-auth.md."
        )


_client: Github | None = None
_token: str | None = None


def get_client() -> Github:
    """Return a singleton authenticated Github client.

    First call performs scope pre-flight. Subsequent calls are free.
    """
    global _client, _token
    if _client is not None:
        return _client
    token = _resolve_token()
    _check_scopes(token)
    _token = token
    _client = Github(auth=Auth.Token(token), per_page=100)
    return _client


def get_token() -> str:
    """Return the cached token (after get_client() has been called)."""
    if _token is None:
        get_client()
    assert _token is not None
    return _token


def graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST a GraphQL query. Raises on transport or GraphQL errors."""
    token = get_token()
    payload = {"query": query, "variables": variables or {}}
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            resp = httpx.post(
                GRAPHQL_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        except httpx.HTTPError as e:
            last_exc = e
            time.sleep(min(2**attempt, MAX_BACKOFF_SECONDS))
            continue
        if resp.status_code == 200:
            data = resp.json()
            if "errors" in data:
                raise RuntimeError(f"GraphQL errors: {data['errors']}")
            return data.get("data") or {}
        if resp.status_code in (403, 429):
            wait = _wait_for_rate_limit(resp.headers, attempt)
            time.sleep(wait)
            continue
        raise RuntimeError(f"GraphQL HTTP {resp.status_code}: {resp.text[:300]}")
    raise RuntimeError(f"GraphQL retries exhausted: {last_exc}")


def _wait_for_rate_limit(headers: httpx.Headers, attempt: int) -> float:
    reset = headers.get("X-RateLimit-Reset")
    retry_after = headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), MAX_BACKOFF_SECONDS)
        except ValueError:
            pass
    if reset:
        try:
            wait = float(reset) - time.time()
            if wait > 0:
                return min(wait + 1, MAX_BACKOFF_SECONDS)
        except ValueError:
            pass
    return min(2**attempt, MAX_BACKOFF_SECONDS)


def retry_on_rate_limit(fn: Callable[..., R]) -> Callable[..., R]:
    """Wrap a PyGithub call with retry/backoff on rate-limit errors."""

    def wrapper(*args: Any, **kwargs: Any) -> R:
        for attempt in range(5):
            try:
                return fn(*args, **kwargs)
            except RateLimitExceededException as e:
                wait = _wait_for_rate_limit(getattr(e, "headers", {}) or {}, attempt)
                time.sleep(wait)
            except GithubException as e:
                # 403 secondary rate limit
                if e.status == 403 and "secondary rate limit" in str(e.data).lower():
                    time.sleep(min(2**attempt, MAX_BACKOFF_SECONDS))
                    continue
                raise
        raise RuntimeError(f"Retries exhausted for {fn.__name__}")

    return wrapper


def list_org_repos(org: str, include_archived: bool = False) -> list[dict[str, Any]]:
    """Return a flat list of repo metadata dicts for an org.

    Uses GraphQL for one paginated query rather than N REST calls.
    """
    repos: list[dict[str, Any]] = []
    cursor: str | None = None
    query = """
    query($org: String!, $cursor: String) {
      organization(login: $org) {
        repositories(first: 100, after: $cursor, isArchived: false) {
          pageInfo { hasNextPage endCursor }
          nodes {
            name
            nameWithOwner
            isArchived
            isFork
            isPrivate
            description
            primaryLanguage { name }
            updatedAt
          }
        }
      }
    }
    """
    while True:
        data = graphql(query, {"org": org, "cursor": cursor})
        block = data["organization"]["repositories"]
        for node in block["nodes"]:
            if node["isArchived"] and not include_archived:
                continue
            repos.append(node)
        if not block["pageInfo"]["hasNextPage"]:
            break
        cursor = block["pageInfo"]["endCursor"]
    return repos


def bounded_map(
    fn: Callable[[T], R],
    items: Iterable[T],
    workers: int = DEFAULT_WORKERS,
) -> Iterator[R]:
    """Run fn over items concurrently with a small thread pool."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(fn, items):
            yield result


def fail_auth(message: str) -> None:
    """Print to stderr and exit 3 (auth/scope error)."""
    print(f"auth error: {message}", file=sys.stderr)
    sys.exit(3)
