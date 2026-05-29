# Clustering Recipes for Scan Output

The agent reads `scan.py`'s JSON in-context and groups items into batches a
maintainer can work through with low context-switching. These recipes
describe what to look for. Apply more than one when natural — items can
appear in multiple clusters.

## Recipe 1: Same error fingerprint across repos

Look at `fingerprints[]`. Group items where any value matches across repos.

- `kind=go_panic` → likely runtime regression, file together.
- `kind=aws_error_code` → API contract / IAM / SDK issue; group by error code.
- `kind=py_traceback` → e2e harness flake; usually one root cause across many e2e suites.

**Why these go together:** one fix in `runtime` or one IAM update often
resolves several issues; reviewing them in one sitting amortizes the
investigation.

## Recipe 2: Same `area/*` label

Group all items carrying the same `area/codegen`, `area/runtime`,
`area/e2e`, etc. label. Useful when one engineer "owns" an area for the
day.

## Recipe 3: Same controller / AWS service

For PRs, the repo (`*-controller`) is the service. For issues, infer from
`service/*` label, `repo` field (if filed against a controller repo), or
title/body keywords.

**Why these go together:** the maintainer who knows the service stays in
their mental model.

## Recipe 4: Complexity buckets

Use label hints + size proxies:

- **Trivial:** `kind/documentation`, `good first issue`, PRs with
  `additions+deletions ≤ 20`, single file changed.
- **Small:** `kind/cleanup`, `kind/test`, PRs touching ≤ 3 files.
- **Medium:** `kind/feature`, `kind/enhancement`, PRs touching ≤ 10 files.
- **Large:** anything above; new resource PRs; `kind/feature` with many
  files.

**Why these go together:** maintainers can budget by bucket — "I'll do
five trivials, then one medium" — instead of mixing context.

## Recipe 5: Cheap wins (rotation-friendly)

Surface separately: items that are easy to land and clear the queue.

- Issues open >90d with no clarifying comment from the team
- PRs failing only on stale base (rebase needed)
- Documentation issues with explicit suggested fix in the body
- `good first issue` items that have no assignee and no recent activity

**Why these go together:** these are "between bigger work" tasks. Often
parked during sprints.

## Recipe 6: Stalled (needs nudging)

- Issues with `triage/needs-information` and last comment age >14d → close
  candidate or re-ping.
- PRs with author response >30d ago and no maintainer follow-up → re-review
  or close.
- Draft PRs >60d → check with author.

## Output format

Present clusters to the user as a table:

| Cluster | Items | Repos | Suggested action |
|---|---|---|---|
| `runtime panic` | 4 | runtime, s3-controller, eks-controller | open root-cause discussion in `community` |
| `area/codegen` | 9 | code-generator, eks-controller, ec2-controller | one engineer batches reviews |
| `cheap wins` | 6 | various | knock out individually |

For each cluster, list member items as `repo#NN — title (labels)` so the
user can pick what to work on next.
