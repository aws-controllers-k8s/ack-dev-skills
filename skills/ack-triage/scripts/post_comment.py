#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyGithub>=2.3",
#   "httpx>=0.27",
# ]
# ///
"""Post a comment to a GitHub issue. Dry-run by default; --apply writes.

Idempotency: refuses to re-post an identical body the same authenticated
user already posted within the last 7 days. --force overrides.

Locked / closed guard: refuses to post unless --force.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))

from confirm import ConfirmOptions, confirm_action, env_dry_run, fail_generic  # noqa: E402
from gh_client import AuthError, fail_auth, get_client  # noqa: E402
from normalize import idempotency_hash  # noqa: E402

DEFAULT_ORG = "aws-controllers-k8s"
DUPLICATE_WINDOW = timedelta(days=7)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True, help="<owner>/<name> or just <name>")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--body-file", required=True, help="path to comment body (markdown)")
    p.add_argument("--apply", action="store_true")
    p.add_argument(
        "--force",
        action="store_true",
        help="bypass idempotency skip and locked/closed guard",
    )
    return p.parse_args()


def resolve_repo(spec: str) -> str:
    return spec if "/" in spec else f"{DEFAULT_ORG}/{spec}"


def main() -> int:
    args = parse_args()
    body_path = pathlib.Path(args.body_file)
    if not body_path.exists():
        fail_generic(f"--body-file not found: {body_path}")
        return 1
    body = body_path.read_text().rstrip() + "\n"
    if not body.strip():
        fail_generic("comment body is empty")
        return 1

    try:
        gh = get_client()
    except AuthError as e:
        fail_auth(str(e))
        return 3

    full_name = resolve_repo(args.repo)
    repo = gh.get_repo(full_name)
    issue = repo.get_issue(args.issue)
    me = gh.get_user().login

    if (issue.state == "closed" or getattr(issue, "locked", False)) and not args.force:
        state_desc = "locked" if getattr(issue, "locked", False) else "closed"
        fail_generic(
            f"refusing to comment on {state_desc} issue {full_name}#{args.issue}; "
            "pass --force to override"
        )
        return 1

    target_hash = idempotency_hash(body.strip())
    cutoff = datetime.now(timezone.utc) - DUPLICATE_WINDOW
    duplicate_url: str | None = None
    if not args.force:
        for c in issue.get_comments():
            if c.user is None or c.user.login != me:
                continue
            ts = c.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
            if idempotency_hash((c.body or "").strip()) == target_hash:
                duplicate_url = c.html_url
                break

    title = (
        f"Comment → {full_name}#{args.issue} (as @{me})"
        + (f"  [DUPLICATE of {duplicate_url}]" if duplicate_url else "")
    )
    preview = body
    if env_dry_run() and args.apply:
        preview = preview + "\n[DRY_RUN=1: writes are disabled]"

    if duplicate_url and not args.force:
        sep = "─" * max(20, min(60, len(title)))
        sys.stdout.write(f"\n{sep}\n{title}\n{sep}\n{preview}\n{sep}\n")
        sys.stdout.write(
            f"skip: identical comment by @{me} posted within {DUPLICATE_WINDOW.days}d "
            f"({duplicate_url}). pass --force to re-post.\n"
        )
        return 0

    opts = ConfirmOptions(apply=args.apply, force=args.force)
    if not confirm_action(title, preview, opts=opts):
        return 0

    new_comment = issue.create_comment(body)
    print(f"posted: {new_comment.html_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
