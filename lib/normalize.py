"""Normalization helpers for issues, PRs, and unified diffs."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

BODY_BUDGET = 8000

# Patterns we extract as "fingerprints" for cross-issue clustering.
_FINGERPRINT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("go_panic", re.compile(r"panic:\s*([^\n]+)", re.IGNORECASE)),
    ("py_traceback", re.compile(r"Traceback \(most recent call last\):")),
    ("aws_error_code", re.compile(r"\b([A-Z][A-Za-z0-9]+(?:Exception|NotFound|Denied|InvalidRequest))\b")),
    ("aws_status_code", re.compile(r"\bstatus code:\s*(\d{3})\b")),
    ("k8s_event", re.compile(r"FailedSync|ReconcileError|StatusReason")),
]


def truncate_body(body: str | None, limit: int = BODY_BUDGET) -> str:
    if not body:
        return ""
    if len(body) <= limit:
        return body
    head = body[: limit - 100]
    return f"{head}\n…[truncated {len(body) - len(head)} chars]…"


def extract_fingerprints(text: str) -> list[dict[str, str]]:
    """Find error / panic / AWS error patterns useful for cross-issue grouping."""
    if not text:
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for label, pat in _FINGERPRINT_PATTERNS:
        for match in pat.finditer(text):
            value = (match.group(1) if match.groups() else match.group(0)).strip()
            value = value[:200]
            key = (label, value)
            if key in seen:
                continue
            seen.add(key)
            out.append({"kind": label, "value": value})
    return out


def normalize_issue(issue: Any) -> dict[str, Any]:
    """PyGithub Issue (or compatible dict) → flat dict."""
    body = getattr(issue, "body", None) or ""
    user = getattr(issue, "user", None)
    return {
        "type": "issue",
        "repo": _repo_full_name(issue),
        "number": issue.number,
        "title": issue.title,
        "state": issue.state,
        "url": issue.html_url,
        "author": getattr(user, "login", None),
        "labels": [_label_name(lbl) for lbl in getattr(issue, "labels", []) or []],
        "comments": issue.comments,
        "created_at": _iso(issue.created_at),
        "updated_at": _iso(issue.updated_at),
        "closed_at": _iso(getattr(issue, "closed_at", None)),
        "body": truncate_body(body),
        "fingerprints": extract_fingerprints(body),
        "is_pull_request": getattr(issue, "pull_request", None) is not None,
    }


def normalize_pr(pr: Any, *, include_diff: bool = False) -> dict[str, Any]:
    """PyGithub PullRequest → flat dict."""
    body = getattr(pr, "body", None) or ""
    user = getattr(pr, "user", None)
    base = getattr(pr, "base", None)
    head = getattr(pr, "head", None)
    out: dict[str, Any] = {
        "type": "pr",
        "repo": _repo_full_name(pr),
        "number": pr.number,
        "title": pr.title,
        "state": pr.state,
        "url": pr.html_url,
        "author": getattr(user, "login", None),
        "labels": [_label_name(lbl) for lbl in getattr(pr, "labels", []) or []],
        "draft": getattr(pr, "draft", False),
        "merged": getattr(pr, "merged", False),
        "mergeable_state": getattr(pr, "mergeable_state", None),
        "additions": getattr(pr, "additions", None),
        "deletions": getattr(pr, "deletions", None),
        "changed_files": getattr(pr, "changed_files", None),
        "base_ref": getattr(base, "ref", None) if base else None,
        "head_ref": getattr(head, "ref", None) if head else None,
        "head_sha": getattr(head, "sha", None) if head else None,
        "created_at": _iso(pr.created_at),
        "updated_at": _iso(pr.updated_at),
        "closed_at": _iso(getattr(pr, "closed_at", None)),
        "merged_at": _iso(getattr(pr, "merged_at", None)),
        "body": truncate_body(body),
        "fingerprints": extract_fingerprints(body),
    }
    if include_diff:
        # Caller fills these in; keep keys present so the JSON shape is stable.
        out["files"] = []
        out["commentable_positions"] = []
    return out


def parse_diff_positions(unified_diff: str) -> list[dict[str, Any]]:
    """Walk a unified diff and return commentable positions per file.

    Each position is `{path, line, side, hunk_idx}` where `line` is the file
    line number on the indicated side. GitHub accepts inline review comments
    only on lines that appear in the diff (added/context for RIGHT,
    removed/context for LEFT).

    Returns a flat list across all files in the diff.
    """
    if not unified_diff:
        return []
    positions: list[dict[str, Any]] = []
    cur_path: str | None = None
    hunk_idx = 0
    new_line = 0
    old_line = 0
    in_hunk = False
    hunk_re = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    for raw in unified_diff.splitlines():
        if raw.startswith("diff --git "):
            cur_path = None
            hunk_idx = 0
            in_hunk = False
            continue
        if raw.startswith("+++ "):
            # +++ b/path/to/file  or  +++ /dev/null
            target = raw[4:].strip()
            if target == "/dev/null":
                cur_path = None
            else:
                cur_path = target[2:] if target.startswith("b/") else target
            continue
        if raw.startswith("--- "):
            continue
        m = hunk_re.match(raw)
        if m:
            old_line = int(m.group(1))
            new_line = int(m.group(2))
            hunk_idx += 1
            in_hunk = True
            continue
        if not in_hunk or cur_path is None:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            positions.append(
                {"path": cur_path, "line": new_line, "side": "RIGHT", "hunk_idx": hunk_idx}
            )
            new_line += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            positions.append(
                {"path": cur_path, "line": old_line, "side": "LEFT", "hunk_idx": hunk_idx}
            )
            old_line += 1
        elif raw.startswith(" "):
            # Context line: commentable on either side, but RIGHT is what
            # reviewers usually want.
            positions.append(
                {"path": cur_path, "line": new_line, "side": "RIGHT", "hunk_idx": hunk_idx}
            )
            new_line += 1
            old_line += 1
        elif raw.startswith("\\"):
            # "\ No newline at end of file" — skip without advancing.
            continue
    return positions


def idempotency_hash(payload: Any) -> str:
    """Stable SHA-256 over a JSON-serializable payload."""
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def render_excerpt(
    patch: str,
    target_line: int,
    side: str,
    *,
    context: int = 3,
    max_width: int = 120,
) -> list[str]:
    """Return a small slice of the patch around (target_line, side).

    `patch` is the per-file patch GitHub gives back via `pull.get_files()` —
    it has hunk headers (`@@ -a,b +c,d @@`) but no `diff --git` / `+++`
    preamble. We walk the hunk that contains the target and return up to
    `context` lines on either side, preserving the original prefix
    (` ` / `+` / `-`). The matching line is annotated with `← here`.

    Lines longer than `max_width` are truncated with `…`. Comments at the
    edge of a hunk just get fewer context lines on that side.

    The list is ready to drop inside a ```diff code fence.
    """
    if not patch:
        return [f"  (no diff context available; comment on {side} line {target_line})"]

    side = side.upper()
    if side not in ("LEFT", "RIGHT"):
        side = "RIGHT"

    hunk_re = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    # Walk the patch, building a list of (prefix, file_line_for_side, raw_line)
    # entries per hunk. Stop once we've found the hunk containing target_line
    # on the requested side.
    in_hunk = False
    new_line = 0
    old_line = 0
    hunk_lines: list[tuple[str, int | None, int | None, str]] = []
    target_idx: int | None = None

    for raw in patch.splitlines():
        m = hunk_re.match(raw)
        if m:
            # Starting a new hunk. If we already found a target, we're done.
            if target_idx is not None:
                break
            old_line = int(m.group(1))
            new_line = int(m.group(2))
            in_hunk = True
            hunk_lines = [("@", None, None, raw)]
            continue
        if not in_hunk:
            continue
        if raw.startswith("\\"):
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            entry = ("+", None, new_line, raw[1:])
            if side == "RIGHT" and new_line == target_line and target_idx is None:
                target_idx = len(hunk_lines)
            new_line += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            entry = ("-", old_line, None, raw[1:])
            if side == "LEFT" and old_line == target_line and target_idx is None:
                target_idx = len(hunk_lines)
            old_line += 1
        elif raw.startswith(" "):
            entry = (" ", old_line, new_line, raw[1:])
            file_line = new_line if side == "RIGHT" else old_line
            if file_line == target_line and target_idx is None:
                target_idx = len(hunk_lines)
            new_line += 1
            old_line += 1
        else:
            # Unexpected line; keep walking.
            continue
        hunk_lines.append(entry)

    if target_idx is None:
        # Target wasn't on a commentable position in this patch. Render the
        # whole most-recent hunk as a fallback so the user gets *something*.
        return [_truncate(_format_excerpt_line(e), max_width) for e in hunk_lines if e[0] != "@"]

    start = max(1, target_idx - context)  # skip index 0 (the @@ line)
    end = min(len(hunk_lines), target_idx + context + 1)

    out: list[str] = []
    for i in range(start, end):
        prefix, _, _, body = hunk_lines[i]
        marker = "  ← here" if i == target_idx else ""
        line = f"{prefix} {body}{marker}"
        out.append(_truncate(line, max_width))
    return out


def _format_excerpt_line(entry: tuple[str, int | None, int | None, str]) -> str:
    prefix, _, _, body = entry
    return f"{prefix} {body}"


def _truncate(line: str, max_width: int) -> str:
    if len(line) <= max_width:
        return line
    return line[: max_width - 1] + "…"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _label_name(lbl: Any) -> str:
    return getattr(lbl, "name", None) or (lbl.get("name") if isinstance(lbl, dict) else str(lbl))


def _repo_full_name(obj: Any) -> str | None:
    repo = getattr(obj, "repository", None) or getattr(obj, "base", None)
    if repo is None:
        return None
    if hasattr(repo, "full_name"):
        return repo.full_name
    if hasattr(repo, "repo"):
        return getattr(repo.repo, "full_name", None)
    return None
