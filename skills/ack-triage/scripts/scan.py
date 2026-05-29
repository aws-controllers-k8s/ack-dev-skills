#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyGithub>=2.3",
#   "httpx>=0.27",
# ]
# ///
"""Cross-repo scan of issues and PRs across an org (default
aws-controllers-k8s). Read-only; emits normalized JSON for the agent to
cluster.

See SKILL.md for usage.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))

from confirm import env_dry_run  # noqa: E402
from gh_client import (  # noqa: E402
    AuthError,
    bounded_map,
    fail_auth,
    get_client,
    list_org_repos,
)
from normalize import normalize_issue, normalize_pr  # noqa: E402

DEFAULT_ORG = "aws-controllers-k8s"
SINCE_RE = re.compile(r"^(\d+)([dwmy])$")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--org", default=DEFAULT_ORG)
    p.add_argument(
        "--types",
        default="issues,prs",
        help="comma-separated subset of: issues, prs, repos",
    )
    p.add_argument("--state", choices=("open", "closed", "all"), default="open")
    p.add_argument(
        "--since",
        default=None,
        help="cutoff for updated_at; ISO date or shorthand like 30d, 2w, 6m, 1y",
    )
    p.add_argument(
        "--repos",
        default=None,
        help="comma-separated repo names (without org prefix) to limit to",
    )
    p.add_argument("--out", default="-", help="output path (- for stdout)")
    p.add_argument(
        "--include-archived",
        action="store_true",
        help="include archived repos (default: skip)",
    )
    return p.parse_args()


def parse_since(spec: str | None) -> datetime | None:
    if spec is None:
        return None
    m = SINCE_RE.match(spec)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = {
            "d": timedelta(days=n),
            "w": timedelta(weeks=n),
            "m": timedelta(days=30 * n),
            "y": timedelta(days=365 * n),
        }[unit]
        return datetime.now(timezone.utc) - delta
    # Try ISO
    try:
        dt = datetime.fromisoformat(spec)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError as e:
        raise SystemExit(f"--since: cannot parse {spec!r} ({e})")


def fetch_for_repo(
    full_name: str, types: set[str], state: str, since: datetime | None
) -> list[dict]:
    gh = get_client()
    repo = gh.get_repo(full_name)
    out: list[dict] = []

    if "issues" in types or "prs" in types:
        # PyGithub get_issues() returns both issues and PRs.
        kwargs: dict = {"state": state, "sort": "updated", "direction": "desc"}
        if since is not None:
            kwargs["since"] = since
        for issue in repo.get_issues(**kwargs):
            is_pr = issue.pull_request is not None
            if is_pr and "prs" not in types:
                continue
            if not is_pr and "issues" not in types:
                continue
            if is_pr:
                # Fetch the PR object for richer fields. One extra call per PR;
                # fine at v1 scale. If perf becomes an issue, switch to GraphQL.
                pr = repo.get_pull(issue.number)
                out.append(normalize_pr(pr))
            else:
                out.append(normalize_issue(issue))
    return out


def main() -> int:
    args = parse_args()
    types = {t.strip() for t in args.types.split(",") if t.strip()}
    valid = {"issues", "prs", "repos"}
    bad = types - valid
    if bad:
        print(f"unknown --types value(s): {sorted(bad)}", file=sys.stderr)
        return 1

    if env_dry_run():
        print("DRY_RUN=1 noted (this script is read-only — no-op).", file=sys.stderr)

    since = parse_since(args.since)

    try:
        repos = list_org_repos(args.org, include_archived=args.include_archived)
    except AuthError as e:
        fail_auth(str(e))
        return 3

    if args.repos:
        keep = {r.strip() for r in args.repos.split(",") if r.strip()}
        repos = [r for r in repos if r["name"] in keep]
        missing = keep - {r["name"] for r in repos}
        if missing:
            print(
                f"warning: --repos referenced unknown repos: {sorted(missing)}",
                file=sys.stderr,
            )

    if "repos" in types and types == {"repos"}:
        result = repos
    else:
        full_names = [r["nameWithOwner"] for r in repos]

        def fetch(name: str) -> list[dict]:
            try:
                return fetch_for_repo(name, types, args.state, since)
            except Exception as e:  # noqa: BLE001
                print(f"warning: {name}: {e}", file=sys.stderr)
                return []

        items: list[dict] = []
        for batch in bounded_map(fetch, full_names):
            items.extend(batch)

        if "repos" in types:
            result = {"repos": repos, "items": items}
        else:
            result = items

    if args.out == "-":
        json.dump(result, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        pathlib.Path(args.out).write_text(
            json.dumps(result, indent=2, default=str) + "\n"
        )
        print(
            f"wrote {len(result) if isinstance(result, list) else 'result'} "
            f"to {args.out}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
