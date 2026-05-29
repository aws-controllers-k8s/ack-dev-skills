#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyGithub>=2.3",
#   "httpx>=0.27",
# ]
# ///
"""Add or remove labels on a GitHub issue. Dry-run by default; --apply writes.

Validation:
  - Labels in --add must appear in the canonical list
    (references/ack-labels.md) OR already exist on the target repo, unless
    --create-missing is passed.
  - Refuses to write to locked or closed issues unless --force.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))

from confirm import ConfirmOptions, confirm_action, fail_generic  # noqa: E402
from gh_client import AuthError, fail_auth, get_client  # noqa: E402

DEFAULT_ORG = "aws-controllers-k8s"
LABEL_DOC = pathlib.Path(__file__).resolve().parents[3] / "references" / "ack-labels.md"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True, help="<owner>/<name> or just <name>")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--add", default="", help="comma-separated labels to add")
    p.add_argument("--remove", default="", help="comma-separated labels to remove")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument(
        "--create-missing",
        action="store_true",
        help="if a label in --add isn't canonical and isn't on the repo, create it",
    )
    return p.parse_args()


def resolve_repo(spec: str) -> str:
    return spec if "/" in spec else f"{DEFAULT_ORG}/{spec}"


def split_csv(value: str) -> list[str]:
    return [s.strip() for s in value.split(",") if s.strip()]


_canonical_cache: set[str] | None = None


def canonical_labels() -> set[str]:
    """Parse references/ack-labels.md for label names.

    Looks for backticked entries that match a kind/, area/, priority/,
    service/, triage/ prefix or one of the bare GitHub defaults. Service
    labels are wildcards — `service/*` matches `service/<anything>`.
    """
    global _canonical_cache
    if _canonical_cache is not None:
        return _canonical_cache
    if not LABEL_DOC.exists():
        _canonical_cache = set()
        return _canonical_cache
    text = LABEL_DOC.read_text()
    out: set[str] = set()
    for m in re.finditer(r"`([^`]+)`", text):
        candidate = m.group(1).strip()
        if "/" not in candidate and candidate not in {"good first issue", "help wanted"}:
            continue
        out.add(candidate)
    _canonical_cache = out
    return out


def is_canonical(label: str) -> bool:
    catalog = canonical_labels()
    if label in catalog:
        return True
    # service/<anything> wildcard
    if label.startswith("service/") and "service/*" in catalog:
        return True
    return False


def main() -> int:
    args = parse_args()
    add = split_csv(args.add)
    remove = split_csv(args.remove)
    if not add and not remove:
        fail_generic("must specify --add and/or --remove")
        return 1

    try:
        gh = get_client()
    except AuthError as e:
        fail_auth(str(e))
        return 3

    full_name = resolve_repo(args.repo)
    repo = gh.get_repo(full_name)
    issue = repo.get_issue(args.issue)

    if (issue.state == "closed" or getattr(issue, "locked", False)) and not args.force:
        state_desc = "locked" if getattr(issue, "locked", False) else "closed"
        fail_generic(
            f"refusing to label {state_desc} issue {full_name}#{args.issue}; "
            "pass --force to override"
        )
        return 1

    repo_labels = {lbl.name for lbl in repo.get_labels()}
    current = {lbl.name for lbl in issue.labels}

    unknown = []
    to_create = []
    for label in add:
        if label in current:
            continue
        if label in repo_labels:
            continue
        if is_canonical(label):
            to_create.append(label)
            continue
        if args.create_missing:
            to_create.append(label)
            continue
        unknown.append(label)

    if unknown:
        fail_generic(
            "unknown labels (not in canonical list and not on the repo): "
            f"{unknown}. Either pick from references/ack-labels.md or pass "
            "--create-missing if the team has decided to add a new label."
        )
        return 1

    will_add = [lbl for lbl in add if lbl not in current]
    will_remove = [lbl for lbl in remove if lbl in current]
    if not will_add and not will_remove:
        print(f"no-op: labels already match (current: {sorted(current) or '[]'})")
        return 0

    title = f"Labels → {full_name}#{args.issue}"
    preview_lines = []
    if will_add:
        preview_lines.append("add:    " + ", ".join(will_add))
    if to_create:
        preview_lines.append("create: " + ", ".join(to_create))
    if will_remove:
        preview_lines.append("remove: " + ", ".join(will_remove))
    preview = "\n".join(preview_lines)

    opts = ConfirmOptions(apply=args.apply, force=args.force)
    if not confirm_action(title, preview, opts=opts):
        return 0

    for label in to_create:
        if label not in repo_labels:
            repo.create_label(name=label, color="ededed")
            print(f"created label {label}")

    for label in will_add:
        issue.add_to_labels(label)
        print(f"added {label}")
    for label in will_remove:
        issue.remove_from_labels(label)
        print(f"removed {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
