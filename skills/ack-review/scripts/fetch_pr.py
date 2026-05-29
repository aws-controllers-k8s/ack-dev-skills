#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyGithub>=2.3",
#   "httpx>=0.27",
# ]
# ///
"""Fetch a PR with diff, files, check runs, linked issues, and the list of
inline-commentable positions. Read-only."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))

from confirm import env_dry_run  # noqa: E402
from gh_client import AuthError, fail_auth, get_client  # noqa: E402
from normalize import normalize_pr, parse_diff_positions, truncate_body  # noqa: E402

DEFAULT_ORG = "aws-controllers-k8s"
LINKED_ISSUE_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:#(\d+)|"
    r"(?:https?://github\.com/([^/]+/[^/]+)/issues/(\d+)))",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True, help="<owner>/<name> or just <name>")
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--out", default="-")
    return p.parse_args()


def resolve_repo(spec: str) -> str:
    return spec if "/" in spec else f"{DEFAULT_ORG}/{spec}"


def find_linked_issues(body: str | None, repo_full_name: str) -> list[dict]:
    if not body:
        return []
    seen: set[tuple[str, int]] = set()
    out: list[dict] = []
    for m in LINKED_ISSUE_RE.finditer(body):
        if m.group(1):
            key = (repo_full_name, int(m.group(1)))
        else:
            key = (m.group(2), int(m.group(3)))
        if key in seen:
            continue
        seen.add(key)
        out.append({"repo": key[0], "number": key[1]})
    return out


def main() -> int:
    args = parse_args()
    if env_dry_run():
        print("DRY_RUN=1 noted (this script is read-only — no-op).", file=sys.stderr)

    try:
        gh = get_client()
    except AuthError as e:
        fail_auth(str(e))
        return 3

    full_name = resolve_repo(args.repo)
    repo = gh.get_repo(full_name)
    pr = repo.get_pull(args.pr)

    pr_data = normalize_pr(pr)

    files: list[dict] = []
    diff_segments: list[str] = []
    for f in pr.get_files():
        files.append(
            {
                "path": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "changes": f.changes,
                "patch": truncate_body(f.patch or "", limit=20000),
            }
        )
        if f.patch:
            # Reconstruct a unified-diff-ish header for parse_diff_positions.
            diff_segments.append(f"diff --git a/{f.filename} b/{f.filename}")
            diff_segments.append(f"--- a/{f.filename}")
            diff_segments.append(f"+++ b/{f.filename}")
            diff_segments.append(f.patch)
    unified = "\n".join(diff_segments)
    positions = parse_diff_positions(unified)

    checks: list[dict] = []
    head_sha = pr.head.sha if pr.head else None
    if head_sha:
        try:
            commit = repo.get_commit(head_sha)
            for run in commit.get_check_runs():
                checks.append(
                    {
                        "name": run.name,
                        "status": run.status,
                        "conclusion": run.conclusion,
                        "url": run.html_url,
                    }
                )
        except Exception as e:  # noqa: BLE001
            print(f"warning: check runs unavailable: {e}", file=sys.stderr)

    out = {
        "pr": pr_data,
        "files": files,
        "commentable_positions": positions,
        "checks": checks,
        "linked_issues": find_linked_issues(pr.body, full_name),
    }

    text = args.out
    payload = json.dumps(out, indent=2, default=str)
    if text == "-":
        sys.stdout.write(payload + "\n")
    else:
        pathlib.Path(text).write_text(payload + "\n")
        print(f"wrote {text}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
