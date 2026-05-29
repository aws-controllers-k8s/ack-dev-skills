---
name: ack-review
description: >-
  First-pass review of a GitHub PR against ACK conventions. Use when a
  maintainer wants to triage incoming PRs or wants a structured walk
  through the ACK rubric (don't edit generated files, renames covers all
  ops, helm chart updated, E2E tests check Synced, etc.). Dry-run produces
  a markdown review; --apply posts a single GitHub review with inline
  comments.
license: Apache-2.0
metadata:
  author: ACK Team
  version: "0.1.0"
---

# ack-review

## When this skill applies

Activate when the user asks to:

- Review a PR (e.g. `s3-controller#42`)
- Do a first-pass review of incoming PRs
- Check a PR against ACK conventions
- Generate review comments to post

For deeper authoring guidance (how the codegen *should* work), use
[`ack-dev`](../ack-dev/SKILL.md). This skill *applies* the rules to a
specific PR.

## Workflow

### 1. Fetch the PR

```bash
uv run skills/ack-review/scripts/fetch_pr.py \
  --repo aws-controllers-k8s/s3-controller \
  --pr 42 \
  --out /tmp/pr.json
```

The JSON includes:
- `pr` — PyGithub-style normalized fields
- `files[]` — per-file diff info: `path`, `status`, `additions`,
  `deletions`, `patch`
- `commentable_positions[]` — pre-computed `{path, line, side, hunk_idx}`
  tuples. **You must pick `(path, line, side)` only from this list** when
  proposing inline comments. Anything else will be rejected by the GitHub
  API as `pull_request_review_comment validation failed`.
- `checks[]` — check-run statuses
- `linked_issues[]` — best-effort matches from PR body

### 2. Walk the rubric

Apply [pr-review-rubric.md](references/pr-review-rubric.md). Each rule
points to where the violation typically lives so you can pick the right
inline coordinate.

### 3. Build the review payload

Write JSON to `/tmp/review.json`:

```json
{
  "event": "COMMENT",
  "body": "Top-level summary in markdown. Use sparingly.",
  "comments": [
    {
      "path": "generator.yaml",
      "line": 42,
      "side": "RIGHT",
      "body": "..."
    }
  ]
}
```

Allowed `event`: `COMMENT`, `REQUEST_CHANGES`. `APPROVE` requires
`--allow-approve` on `post_review.py` and is **rare** — almost never the
right default for an automated first pass.

### 4. Dry-run review

```bash
uv run skills/ack-review/scripts/post_review.py \
  --repo aws-controllers-k8s/s3-controller \
  --pr 42 \
  --review-file /tmp/review.json \
  --pr-file /tmp/pr.json
```

Renders the review as a human-readable markdown preview: the summary
body, then each inline comment grouped by file, with **3 lines of diff
context** before and after the commented line (the line itself marked
`← here`), plus a link to the GitHub view. Posts nothing.

`--pr-file` is optional but recommended in dry-run — it lets the
renderer pull patches from the cached `pr.json` produced by `fetch_pr.py`
without hitting the GitHub API. Without `--pr-file`, dry-run shows
coordinates without diff context.

> **Surface the rendered markdown in the main reply, not just tool
> output.** The script's stdout lives in the collapsed tool-output panel;
> the user shouldn't need `ctrl+o` to see it. After running
> `post_review.py` in dry-run, copy its full stdout verbatim into your
> next assistant message so Claude Code renders it inline. Then ask for
> approval. Don't paraphrase or summarize.
>
> **Never show the raw `review.json` to the user.** Always render via
> `post_review.py` (without `--apply`) first.

### 5. Apply

```bash
uv run skills/ack-review/scripts/post_review.py \
  --repo aws-controllers-k8s/s3-controller \
  --pr 42 \
  --review-file /tmp/review.json \
  --apply
```

The script:
- Validates each comment's `(path, line, side)` against the PR's current
  diff. Invalid coords abort before any API call.
- Drops comments that match a payload posted by the same user within the
  last 7 days (idempotency). `--force` overrides.
- If everything is a duplicate, exits 0 with a clear message and posts
  nothing.
- Otherwise prompts `[y/N]` once, then POSTs a single
  `POST /repos/:o/:r/pulls/:n/reviews` so all inline comments arrive as
  one review thread.

For `event=APPROVE`, add `--allow-approve`. The script refuses without
that flag.

## Conventions and constraints

- **Default to `event=COMMENT`.** Pick `REQUEST_CHANGES` only when at least
  one inline comment names a clear blocker (e.g. edits to a generated
  file). Never pick `APPROVE` automatically.
- **Pick coordinates from `commentable_positions` only.** Don't guess line
  numbers; the agent has the list.
- **Refer to canonical guidance, don't repeat it.** When pointing out a
  violation, link to the relevant section of `ack-dev/SKILL.md` instead of
  re-explaining the rule.
- **Keep summary `body` short.** A two-sentence summary is plenty. Detail
  belongs in inline comments.
- **One review, not N.** The script intentionally batches inline comments
  into a single review API call. Don't try to post comments individually.

## Reference files

- [pr-review-rubric.md](references/pr-review-rubric.md) — what to check
  on every ACK PR.
- The companion [`ack-dev`](../ack-dev/SKILL.md) skill — the source of
  truth for ACK rules; this skill applies them.
- Repo-root [`references/dry-run-conventions.md`](../../references/dry-run-conventions.md)
  — flag/exit-code contract.
