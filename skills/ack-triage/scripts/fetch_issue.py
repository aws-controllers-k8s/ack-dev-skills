#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyGithub>=2.3",
#   "httpx>=0.27",
# ]
# ///
"""Fetch a single issue with its comments and labels. Read-only."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))

from confirm import env_dry_run  # noqa: E402
from gh_client import AuthError, fail_auth, get_client  # noqa: E402
from normalize import normalize_issue, truncate_body  # noqa: E402

DEFAULT_ORG = "aws-controllers-k8s"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True, help="<owner>/<name> or just <name>")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--out", default="-")
    return p.parse_args()


def resolve_repo(spec: str) -> str:
    return spec if "/" in spec else f"{DEFAULT_ORG}/{spec}"


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
    issue = repo.get_issue(args.issue)

    out = normalize_issue(issue)
    out["locked"] = bool(getattr(issue, "locked", False))
    out["assignees"] = [a.login for a in getattr(issue, "assignees", []) or []]
    out["milestone"] = getattr(getattr(issue, "milestone", None), "title", None)

    comments = []
    for c in issue.get_comments():
        comments.append(
            {
                "id": c.id,
                "author": c.user.login if c.user else None,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "body": truncate_body(c.body or ""),
            }
        )
    out["comment_thread"] = comments

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
