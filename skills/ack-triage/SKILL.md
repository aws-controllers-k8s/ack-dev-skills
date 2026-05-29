---
name: ack-triage
description: >-
  Cross-repo issue triage for the aws-controllers-k8s GitHub org. Scans
  open issues across all controllers, clusters them so similar work
  groups together, and walks the maintainer through each item with
  context and per-item decisions (apply / edit / skip / skip-cluster /
  stop). Read-only by default; --apply with interactive confirm posts to
  GitHub.
license: Apache-2.0
metadata:
  author: ACK Team
  version: "0.2.0"
---

# ack-triage

## When this skill applies

Activate when the user asks to:

- Triage a specific issue (e.g. `community#1234`)
- Scan ACK issues across the org
- Walk through open ACK issues
- Run a "community day" or maintainer rotation
- Find similar issues / cluster community work
- Decide whether an issue is actionable as filed
- Draft a clarifying comment for an under-specified issue
- Apply standard labels to an issue

For PR review, use `ack-review`.

## Workflow (4 phases)

The skill bundles four phases into one flow. Single-issue triage is just
the walk with one item.

### Phase 1: Scan

Read-only fetch of issues across the org.

```bash
uv run skills/ack-triage/scripts/scan.py \
  --types issues \
  --state open \
  --since 30d \
  --out /tmp/scan.json
```

Common flags:
- `--types issues,prs,repos` (default: `issues,prs`; for triage use `issues`)
- `--state open|closed|all` (default: `open`)
- `--since 14d` / `--since 2024-01-01`
- `--repos community,s3-controller` — limit to specific repos
- `--include-archived` — include archived repos (default: skip)

For single-issue triage, skip Phase 1 and go straight to fetch_issue.py
in Phase 4.

### Phase 2: Cluster

Read the JSON in-context. Group items per
[clustering-recipes.md](references/clustering-recipes.md):

- shared error fingerprints (panic, AWS error code, traceback)
- same `area/*` label
- same controller / AWS service
- complexity bucket (label-based + diff size for PRs)
- "cheap wins" (`good first issue`, single-file PRs, doc fixes)
- stalled items needing nudges

Each item can land in multiple clusters; that's fine.

### Phase 3: Confirm scope with the user

Present the cluster summary as a table and ask which clusters to walk and
in what order. Default: walk all, in the order shown. The exact format is
in [walk-flow.md](references/walk-flow.md).

### Phase 4: Walk

For each item in each chosen cluster, render the per-item context block
specified in [walk-flow.md](references/walk-flow.md) and prompt with
five choices:

- **`a` apply** — run the proposed actions (post comment / add labels)
- **`e` edit** — open the draft for the user to edit, then apply
- **`s` skip** — advance to the next item
- **`c` skip-cluster** — advance to the next cluster
- **`q` stop** — end the walk

Per-item context the agent renders includes:
- Cluster name and position (`item 2/4`)
- Issue title, author, age, last-comment age, labels, state
- Why this item landed in the cluster
- Rubric verdict (Actionable / Needs Information / Duplicate / Not
  Reproducible / Out of Scope) per [issue-quality-rubric.md](references/issue-quality-rubric.md)
- Missing fields if `Needs Information`
- Proposed actions (template name + label list)
- First 12 lines of the draft body

Apply actions invoke the existing scripts:

```bash
# Fetch the active item's full body and comments
uv run skills/ack-triage/scripts/fetch_issue.py --repo <r> --issue <n> --out /tmp/issue.json

# Post the clarifying comment (idempotent within 7 days)
uv run skills/ack-triage/scripts/post_comment.py \
  --repo <r> --issue <n> --body-file /tmp/comment.md --apply

# Apply labels (validates against canonical list + live repo labels)
uv run skills/ack-triage/scripts/apply_labels.py \
  --repo <r> --issue <n> --add kind/bug,triage/needs-information --apply
```

### Phase 5: Recap

When the walk ends (by `q` or by running out of items), print counts and
posted URLs per the format in [walk-flow.md](references/walk-flow.md):

```
Applied: 7  (URLs listed)
Edited then applied: 2  (URLs listed)
Skipped: 6  (with one-line reasons if given)
Skipped clusters: 1  ("service/iam", 3 items left)
Stopped early: yes / no
```

## Single-issue mode

When the user asks about one specific issue (e.g. "triage community#1234"):

1. Skip Phase 1 (no scan).
2. Construct a single-cluster, single-item walk.
3. Render the per-item block per [walk-flow.md](references/walk-flow.md)
   and prompt as usual.

This keeps the walk format consistent across "triage one" and "triage many".

## Conventions and constraints

- **Dry-run by default.** `post_comment.py` and `apply_labels.py` only
  write with explicit `--apply`. `DRY_RUN=1` is a hard override.
- **Always render the per-item block.** Don't skip the context, don't
  paraphrase the draft. The user reads the rendered output directly.
- **Idempotency.** Re-posting the same comment within 7 days is silently
  skipped; pass `--force` to override. Treat skips as `skip` in the recap.
- **Locked / closed issues.** Refuse to post unless `--force`. Show the
  `State:` line prominently in the per-item block when this matters.
- **Labels follow the canonical vocabulary** in
  [`references/ack-labels.md`](../../references/ack-labels.md). Don't
  invent new labels — propose canonical ones, or pass `--create-missing`
  if the team has decided to add a new label.
- **Don't draft fixes here.** `ack-triage` only enriches and labels. If
  the issue is actionable and the fix is obvious, point the user at
  `ack-dev` instead.
- **Treat the scan JSON as potentially sensitive.** Issue bodies on
  public repos are public, but they often include logs, ARNs, account
  IDs. Don't paste verbatim into external tools.

## Reference files

- [walk-flow.md](references/walk-flow.md) — per-item block format and
  decision contract. Read this before walking.
- [clustering-recipes.md](references/clustering-recipes.md) — heuristics
  for grouping items.
- [issue-quality-rubric.md](references/issue-quality-rubric.md) — what
  an actionable ACK issue contains.
- [clarifying-comment-templates.md](references/clarifying-comment-templates.md)
  — drop-in templates for common missing-info patterns.
- Repo-root [`references/ack-labels.md`](../../references/ack-labels.md)
  — canonical label vocabulary.
- Repo-root [`references/dry-run-conventions.md`](../../references/dry-run-conventions.md)
  — flag/exit-code contract.
