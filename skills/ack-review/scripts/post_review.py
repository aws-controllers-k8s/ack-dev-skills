#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyGithub>=2.3",
#   "httpx>=0.27",
# ]
# ///
"""Render or post a structured GitHub PR review.

Input: a JSON file produced by the agent:

  {
    "event": "COMMENT" | "REQUEST_CHANGES" | "APPROVE",
    "body": "summary markdown",
    "comments": [
      {"path": "...", "line": N, "side": "RIGHT" | "LEFT", "body": "..."}
    ]
  }

Behavior:
  - Default (no --apply): renders a markdown preview and exits.
  - --apply: validates coordinates against the PR's current diff, drops
    duplicates posted by the same user within the last 7 days, prompts
    once, then POSTs a single review.
  - APPROVE requires --allow-approve.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))

from confirm import ConfirmOptions, confirm_action, env_dry_run, fail_generic  # noqa: E402
from gh_client import AuthError, fail_auth, get_client  # noqa: E402
from normalize import idempotency_hash, parse_diff_positions, render_excerpt  # noqa: E402

DEFAULT_ORG = "aws-controllers-k8s"
DUPLICATE_WINDOW = timedelta(days=7)
ALLOWED_EVENTS = {"COMMENT", "REQUEST_CHANGES", "APPROVE"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--review-file", required=True)
    p.add_argument(
        "--pr-file",
        default=None,
        help="optional path to pr.json from fetch_pr.py; used by dry-run to "
        "render diff context without re-fetching",
    )
    p.add_argument("--apply", action="store_true")
    p.add_argument("--force", action="store_true", help="bypass duplicate skip")
    p.add_argument(
        "--allow-approve",
        action="store_true",
        help="allow event=APPROVE; default refuses",
    )
    return p.parse_args()


def resolve_repo(spec: str) -> str:
    return spec if "/" in spec else f"{DEFAULT_ORG}/{spec}"


def render_markdown(
    payload: dict,
    repo: str,
    pr: int,
    *,
    patches: dict[str, str] | None = None,
    skipped_count: int = 0,
) -> str:
    """Render a human-readable review preview.

    `patches` maps file path → unified-diff patch (the per-file `patch`
    field PyGithub returns from `pull.get_files()`). When supplied, each
    inline comment renders with 3 lines of diff context around the
    commented line. Without it, the preview falls back to a coordinate-
    only line.
    """
    patches = patches or {}
    comments = payload.get("comments") or []
    event = payload.get("event", "COMMENT")
    pr_url = f"https://github.com/{repo}/pull/{pr}"

    lines: list[str] = [
        f"# Review draft → {repo}#{pr}",
        f"<{pr_url}>",
        "",
        f"**Event:** `{event}`  ·  **Inline comments:** {len(comments)}",
        "",
    ]
    body = (payload.get("body") or "").strip()
    if body:
        lines.append("## Summary")
        lines.append("")
        lines.append(body)
        lines.append("")

    # Group comments by file (preserve first-seen order).
    by_file: dict[str, list[dict]] = {}
    for c in comments:
        by_file.setdefault(c["path"], []).append(c)

    for path, items in by_file.items():
        lines.append(f"## `{path}`  ·  {len(items)} comment(s)")
        lines.append("")
        for c in items:
            line = int(c["line"])
            side = c.get("side") or "RIGHT"
            anchor = f"R{line}" if side == "RIGHT" else f"L{line}"
            lines.append(f"### line {line} ({side})")
            lines.append("")
            patch = patches.get(path)
            excerpt = render_excerpt(patch or "", line, side)
            lines.append("```diff")
            lines.extend(excerpt)
            lines.append("```")
            lines.append("")
            lines.append((c.get("body") or "").strip())
            lines.append("")
            lines.append(f"[view on github]({pr_url}/files#{anchor})")
            lines.append("")

    if skipped_count:
        lines.append(f"_(skipped {skipped_count} duplicate comment(s))_")
        lines.append("")

    return "\n".join(lines)


def patches_from_pr_file(pr_file: pathlib.Path) -> dict[str, str]:
    """Load patches keyed by path from a pr.json produced by fetch_pr.py."""
    try:
        data = json.loads(pr_file.read_text())
    except (OSError, json.JSONDecodeError) as e:
        fail_generic(f"--pr-file unreadable: {e}")
        return {}
    files = data.get("files") or []
    return {f["path"]: f.get("patch") or "" for f in files if "path" in f}


def patches_from_github(files: list) -> dict[str, str]:
    """Build a path→patch map from PyGithub PullRequestFile objects."""
    return {f.filename: (f.patch or "") for f in files}


def build_position_set(files: list) -> set[tuple[str, int, str]]:
    """Reconstruct commentable positions from a PR's files."""
    segments = []
    for f in files:
        if f.patch:
            segments.append(f"diff --git a/{f.filename} b/{f.filename}")
            segments.append(f"--- a/{f.filename}")
            segments.append(f"+++ b/{f.filename}")
            segments.append(f.patch)
    positions = parse_diff_positions("\n".join(segments))
    return {(p["path"], p["line"], p["side"]) for p in positions}


def main() -> int:
    args = parse_args()
    review_path = pathlib.Path(args.review_file)
    if not review_path.exists():
        fail_generic(f"--review-file not found: {review_path}")
        return 1
    try:
        payload = json.loads(review_path.read_text())
    except json.JSONDecodeError as e:
        fail_generic(f"--review-file is not valid JSON: {e}")
        return 1

    event = (payload.get("event") or "COMMENT").upper()
    if event not in ALLOWED_EVENTS:
        fail_generic(f"event must be one of {sorted(ALLOWED_EVENTS)}; got {event!r}")
        return 1
    if event == "APPROVE" and not args.allow_approve:
        fail_generic(
            "event=APPROVE refused. Pass --allow-approve to override. "
            "Automated APPROVE is rarely correct for a first-pass review."
        )
        return 1

    body = (payload.get("body") or "").strip()
    comments = payload.get("comments") or []
    if not isinstance(comments, list):
        fail_generic("comments must be a list")
        return 1
    for i, c in enumerate(comments):
        for k in ("path", "line", "body"):
            if c.get(k) in (None, ""):
                fail_generic(f"comments[{i}] missing required field: {k}")
                return 1
        if c.get("side") not in (None, "LEFT", "RIGHT"):
            fail_generic(f"comments[{i}].side must be LEFT or RIGHT")
            return 1

    full_name = resolve_repo(args.repo)

    # Dry-run: render and exit, never touch GitHub.
    if not args.apply or env_dry_run():
        patches: dict[str, str] = {}
        if args.pr_file:
            pr_file_path = pathlib.Path(args.pr_file)
            if pr_file_path.exists():
                patches = patches_from_pr_file(pr_file_path)
            else:
                print(
                    f"warning: --pr-file not found: {pr_file_path}; "
                    "rendering without diff context",
                    file=sys.stderr,
                )
        sys.stdout.write(
            render_markdown(payload, full_name, args.pr, patches=patches) + "\n"
        )
        if env_dry_run() and args.apply:
            print("DRY_RUN=1 set: writes are disabled.", file=sys.stderr)
        else:
            print("(dry-run; pass --apply to post)", file=sys.stderr)
        return 0

    try:
        gh = get_client()
    except AuthError as e:
        fail_auth(str(e))
        return 3

    repo = gh.get_repo(full_name)
    pr = repo.get_pull(args.pr)
    me = gh.get_user().login

    # Validate coordinates.
    files = list(pr.get_files())
    valid = build_position_set(files)
    invalid = []
    for c in comments:
        side = c.get("side") or "RIGHT"
        if (c["path"], int(c["line"]), side) not in valid:
            invalid.append(f"{c['path']}:{c['line']}({side})")
    if invalid:
        fail_generic(
            "comment coordinates not in the PR diff (use commentable_positions "
            f"from fetch_pr.py): {invalid}"
        )
        return 1

    # Idempotency: drop comments matching a same-user post in last 7 days.
    cutoff = datetime.now(timezone.utc) - DUPLICATE_WINDOW
    existing_hashes: set[str] = set()
    if not args.force:
        # Issue-level review summaries.
        for r in pr.get_reviews():
            if r.user is None or r.user.login != me:
                continue
            ts = r.submitted_at or r.created_at if hasattr(r, "created_at") else None
            if ts is None:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
            if r.body:
                existing_hashes.add(idempotency_hash(r.body.strip()))
        # Review comments (inline).
        for rc in pr.get_review_comments():
            if rc.user is None or rc.user.login != me:
                continue
            ts = rc.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
            existing_hashes.add(
                idempotency_hash(
                    (rc.path, rc.line or rc.original_line, rc.side or "RIGHT", (rc.body or "").strip())
                )
            )

    body_is_dup = bool(body) and idempotency_hash(body) in existing_hashes
    kept_comments = []
    skipped = []
    for c in comments:
        h = idempotency_hash(
            (c["path"], int(c["line"]), c.get("side") or "RIGHT", c["body"].strip())
        )
        if h in existing_hashes:
            skipped.append(f"{c['path']}:{c['line']}")
            continue
        kept_comments.append(c)

    if not kept_comments and (body_is_dup or not body):
        print(
            f"skip: all comments are duplicates within {DUPLICATE_WINDOW.days}d "
            f"(body_is_dup={body_is_dup}, skipped={skipped}). "
            "pass --force to re-post.",
            file=sys.stderr,
        )
        return 0

    final_body = "" if body_is_dup else body
    title = f"Review → {full_name}#{args.pr} (event={event}, as @{me})"
    preview = render_markdown(
        {"event": event, "body": final_body, "comments": kept_comments},
        full_name,
        args.pr,
        patches=patches_from_github(files),
        skipped_count=len(skipped),
    )

    opts = ConfirmOptions(apply=args.apply, force=args.force)
    if not confirm_action(title, preview, opts=opts):
        return 0

    api_comments = [
        {
            "path": c["path"],
            "line": int(c["line"]),
            "side": c.get("side") or "RIGHT",
            "body": c["body"],
        }
        for c in kept_comments
    ]
    review = pr.create_review(body=final_body, event=event, comments=api_comments)
    print(f"posted: {review.html_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
