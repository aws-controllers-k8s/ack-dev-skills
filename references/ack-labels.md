# ACK Label Vocabulary (Canonical)

Used by `ack-triage`'s `apply_labels.py` to validate label additions before
posting them. Labels not in this list (and not already present on the
target repo) are refused unless `--create-missing` is set.

The list is descriptive — it reflects how the ACK team labels things today.
When the team's conventions change, update this file and the live repo
labels together.

## kind/*

| Label | When to use |
|---|---|
| `kind/bug` | A defect in shipped behavior (controller, codegen, runtime) |
| `kind/feature` | New capability — new resource, new field, new option |
| `kind/enhancement` | Improvement to existing capability |
| `kind/documentation` | Docs-only change |
| `kind/test` | Test-only change (new e2e, fixed flake, refactor) |
| `kind/cleanup` | Refactor, dead code removal, chore |
| `kind/question` | A user question, not yet a bug or feature |

## area/*

| Label | When to use |
|---|---|
| `area/codegen` | `code-generator` repo or generator.yaml-driven behavior |
| `area/runtime` | `runtime` repo / shared reconciliation logic |
| `area/e2e` | E2E tests, `test-infra`, prow jobs |
| `area/release` | Release tooling, version bumps, ATTRIBUTION.md |
| `area/helm` | Helm chart generation or content |
| `area/crd` | CRD definition / generation |
| `area/references` | Cross-resource references (`AWSResourceReferenceWrapper`) |
| `area/ack-generate` | The `ack-generate` CLI itself |

## priority/*

| Label | When to use |
|---|---|
| `priority/critical-urgent` | Outage / data loss / security |
| `priority/important-soon` | Should be tackled within the current cycle |
| `priority/important-longterm` | Wanted, not blocking |
| `priority/awaiting-more-evidence` | Needs more info to be actionable |

## service/*

`service/<aws-service-name>` — applied to issues that target a specific AWS
service controller. Examples: `service/s3`, `service/ec2`, `service/eks`.

The agent should infer the service from the issue body and / or the repo
the PR lives in.

## triage/*

| Label | When to use |
|---|---|
| `triage/needs-information` | Issue is under-specified; clarifying comment posted |
| `triage/duplicate` | Already tracked by another issue |
| `triage/not-reproducible` | Couldn't reproduce on the reported version |
| `triage/accepted` | Confirmed and ready for someone to pick up |

## help wanted / good first issue

Default GitHub labels — used as-is. Apply when an issue is small enough for
a new contributor or when the team specifically wants community help.

| Label | When to use |
|---|---|
| `good first issue` | Self-contained, well-scoped, low context required |
| `help wanted` | Team would welcome an outside contribution |
