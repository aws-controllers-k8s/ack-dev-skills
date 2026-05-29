# Walk Flow — Per-Item Context and Decision Contract

This file specifies how the agent walks a clustered list of issues with
the user. Every per-item prompt MUST follow this format. Don't paraphrase
issue bodies, don't skip context lines, don't invent options.

## Scope confirmation (before the walk starts)

After clustering the scan output (per
[clustering-recipes.md](clustering-recipes.md)), present the cluster
summary table:

```
Found 18 items in 5 clusters from the last 30d.

| # | Cluster              | Items | Repos                              |
|---|----------------------|-------|------------------------------------|
| 1 | runtime panic        | 4     | runtime, s3-controller, eks-ctrl   |
| 2 | area/codegen         | 7     | code-generator, ec2-controller     |
| 3 | service/iam          | 3     | iam-controller                     |
| 4 | cheap wins           | 2     | dev-tools, community               |
| 5 | stalled (>14d)       | 2     | community, eks-controller          |

Walk all clusters in this order? Or pick a subset (e.g. "1, 4")?
```

Defaults: walk all, in the order shown. Honor explicit subset/order from
the user.

## Per-item context block

For every item the walk visits, render exactly this block:

```
─────────────────────────────────────────────
Cluster: <cluster-name> (item <n>/<total-in-cluster>)
Item:    <repo>#<number>
URL:     https://github.com/<repo>/issues/<number>
Title:   "<title>"
Author:  @<login>  ·  filed <Nd> ago  ·  last comment <Nd> ago
Labels:  <comma-separated>  (or "none")
State:   open / closed / locked

Why clustered:
  <one or two sentences naming the specific signal — fingerprint,
  shared label, repo, complexity bucket, etc. Always concrete.>

Rubric verdict: <Actionable | Needs Information | Duplicate | Not Reproducible | Out of Scope>
Missing fields (if Needs Information):
  - <field 1>
  - <field 2>

Proposed actions:
  1. <action 1, e.g. "post Template A (missing reproducer)">
  2. <action 2, e.g. "add labels: triage/needs-information, kind/bug">

[draft preview — first 12 lines]
> <line 1 of draft>
> <line 2>
> ...
─────────────────────────────────────────────
Apply? [a]pply / [e]dit / [s]kip / [c]skip-cluster / [q]stop
```

Required fields:
- **Cluster + position:** Always show "item N of M" so the user knows
  where they are.
- **Issue summary:** title, author, age, last-comment age, labels, state.
- **Why clustered:** one or two sentences naming the *specific* signal
  that put this item in the cluster. Don't just repeat the cluster name.
- **Rubric verdict + missing fields:** from
  [issue-quality-rubric.md](issue-quality-rubric.md).
- **Proposed actions:** numbered, concrete. Include the template name
  (Template A/B/.../G) when posting a clarifying comment.
- **Draft preview:** first 12 lines of the body the agent would post.
  Truncate longer with `…(N more lines)`.

If `Rubric verdict = Actionable`, "Proposed actions" is usually just
"none — actionable as filed" with `kind/*` and `priority/*` label
suggestions. Don't draft a clarifying comment for an actionable issue.

## Decision contract

Five choices. Don't invent more.

| Choice | Effect |
|---|---|
| **`a` apply** | Run the proposed actions: `post_comment.py --apply` and/or `apply_labels.py --apply`. On idempotency duplicate or locked-issue refusal, report the script's message and treat as skip. On success, capture the comment URL for the recap |
| **`e` edit** | Write the draft to `/tmp/comment-<repo>-<n>.md`, ask the user to edit and confirm. Re-render the per-item block with the edited body, then proceed as `apply`. Editing is **draft-only** — labels are committed, not edited |
| **`s` skip** | No action; advance to the next item in the same cluster (or the first item of the next cluster if this was the last) |
| **`c` skip-cluster** | No action; advance to the first item of the next cluster, leaving remaining items in the current cluster untouched |
| **`q` stop** | End the walk immediately; print recap |

Treat any input that's not `a`/`e`/`s`/`c`/`q` (case-insensitive) as
"please clarify"; reprompt without advancing.

## End-of-walk recap

When the walk ends (whether by `q` or by exhausting all items), print:

```
─────────────────────────────────────────────
Walk complete.

Applied: 7
  - https://github.com/aws-controllers-k8s/community/issues/1234#issuecomment-...
  - https://github.com/aws-controllers-k8s/s3-controller/issues/77#issuecomment-...
  - ...

Edited then applied: 2
  - https://github.com/...

Skipped: 6
  - community#1100 — needs research
  - eks-controller#88 — duplicate of community#1234

Skipped clusters: 1
  - "service/iam" (3 items left untouched)

Stopped early: yes (5 items remained)
─────────────────────────────────────────────
```

Required fields:
- Counts for each outcome
- Posted URLs for `apply` and `edit-then-apply` (one per line, full URL)
- For `skip`: the item identifier and a one-line reason if the user gave one
- For `skip-cluster`: the cluster name and how many items were left
- "Stopped early" line iff the walk ended via `q`

## What the agent must NOT do

- Don't show all items at once and ask the user to pick — that defeats
  the walk.
- Don't auto-apply without prompting per item, even when the action is
  obvious. The walk's value is the prompt.
- Don't fabricate "why clustered" — if the cluster grouping was loose,
  say so explicitly ("grouped by `kind/bug` only — no shared fingerprint").
- Don't skip the draft preview. The user shouldn't have to go look at
  the template file.
- Don't include closed or locked items in the walk (they're filtered
  out by `scan.py`'s `--state open` default; if the user requested
  closed-state scanning, the per-item block must show `State: closed`
  prominently and the proposed action will likely be `skip`).
