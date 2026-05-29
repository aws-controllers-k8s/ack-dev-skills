# PR Review Rubric (ACK)

Use this checklist as a structured walk through an incoming ACK PR. Each
row names what to check, where it usually lives in the diff, and the
canonical link in [`ack-dev/SKILL.md`](../../ack-dev/SKILL.md) so review
comments can refer to it instead of repeating the rule.

The rubric is deliberately ACK-specific. Generic review concerns (style,
naming, etc.) are out of scope here — pick those up only if they're severe
enough to block.

## A. Generated-file edits (blocker)

**Rule:** Never manually edit files in `apis/v1alpha1/`, `pkg/resource/`,
`config/crd/`, `config/rbac/`, `helm/`, or `cmd/controller/main.go`. Fix
`generator.yaml` and rebuild instead.

**Where it shows up:** changes touching those directories without a
corresponding `generator.yaml` change, or with a manual override that
reverts on rebuild.

**Severity:** REQUEST_CHANGES if the diff edits generated files directly.

**Reference:** [Golden Rules in ack-dev/SKILL.md](../../ack-dev/SKILL.md#golden-rules).

## B. `renames:` covers all operations

**Rule:** When a field is renamed, every operation that references it
must have the rename declared (Create, Read, Update, Delete, List —
plus `output_fields` for AWS-assigned identifiers). Missing operations
cause `could not find field with path` codegen errors.

**Where it shows up:** new `renames:` block in `generator.yaml`. Diff
inputs/outputs of each `*BackupVault`-style operation.

**Severity:** REQUEST_CHANGES if any operation is missing.

**Reference:** [Adding a New Field](../../ack-dev/SKILL.md#adding-a-new-field-to-a-crd).

## C. Field immutability

**Rule:** Mark `is_immutable: true` for primary keys and AWS lookup
identifiers, even when the API marks them "required" in Update.

**Where it shows up:** new field in `fields:` block of `generator.yaml`.

**Severity:** REQUEST_CHANGES when a primary key or lookup identifier is
left mutable.

**Reference:** [Field Immutability](../../ack-dev/SKILL.md#adding-a-new-field-to-a-crd).

## D. Tag handling

**Rule:** `tags.ignore: true` for resources that don't support TagResource.
Default is `false`. Get this wrong and reconciliation loops or
permission errors at runtime.

**Where it shows up:** `tags:` block per resource in `generator.yaml`.

**Severity:** REQUEST_CHANGES if mismatched against AWS docs.

**Reference:** [Configuring Tags Support](../../ack-dev/SKILL.md#configuring-tags-support).

## E. Cross-resource references

**Rule:** Don't set `service_name` for same-service references. Setting it
even correctly causes generated code to import an undefined alias and
break compilation.

**Where it shows up:** `references:` block under a field in
`generator.yaml`.

**Severity:** REQUEST_CHANGES.

**Reference:** [Implementing Cross-Resource References](../../ack-dev/SKILL.md#implementing-cross-resource-references).

## F. Error code mapping

**Rule:** Prefer `exceptions.errors.404.code` over a custom hook. Many AWS
APIs return non-standard 4xx codes for not-found.

**Where it shows up:** new custom hook templates in `templates/hooks/`
that only map errors.

**Severity:** COMMENT — suggest the declarative form.

**Reference:** [Error Codes and Custom Hooks](../../ack-dev/SKILL.md#error-codes-and-custom-hooks).

## G. Helm chart updated

**Rule:** `helm/crds/`, `helm/values.yaml` (`reconcile.resources` list),
and `helm/templates/cluster-role-controller.yaml` must change alongside
new resources. `make build-controller` produces these — `git status`
should show them.

**Where it shows up:** absence of helm files in a new-resource PR.

**Severity:** REQUEST_CHANGES if missing.

**Reference:** [Common Misses](../../ack-dev/references/pr-workflow.md#common-misses).

## H. E2E tests check `Synced`

**Rule:** Tests must `assert_synced` (or equivalent) after CRUD operations.
"It got created" is not enough — reconciliation needs to converge.

**Where it shows up:** `test/e2e/tests/test_<resource>.py`.

**Severity:** REQUEST_CHANGES if missing for a new resource.

**Reference:** [Pre-Submit Checklist](../../ack-dev/SKILL.md#pre-submit-checklist).

## I. Single squashed commit

**Rule:** PRs should land as a single commit per resource (or per logical
change). Multi-commit PRs make releases noisy.

**Where it shows up:** PR commit list.

**Severity:** COMMENT — request squash before merge.

**Reference:** [Golden Rules](../../ack-dev/SKILL.md#golden-rules).

## J. New-controller bootstrap requirements

For Bootstrap PRs only (new controller). All these are required:

- `Makefile`, `OWNERS`, `OWNERS_ALIASES`, `ATTRIBUTION.md`,
  `config/iam/recommended-inline-policy`
- `OWNERS_ALIASES` does **not** list users no longer in the org
- All resources are in `ignore.resource_names`

**Severity:** REQUEST_CHANGES if any required file missing.

**Reference:** [Bootstrap PR](../../ack-dev/references/pr-workflow.md#1-bootstrap-pr).

## K. Release PR specifics

For Release PRs only:

- Branch named `release-v<version>`
- Commit message: `Release artifacts for release v<version>`
- Single commit
- Version bump matches semver (micro for fixes, minor for new fields/resources)

**Severity:** REQUEST_CHANGES on naming/format issues; merge usually
blocks anyway via prow.

**Reference:** [Release PRs](../../ack-dev/references/pr-workflow.md#3-release-prs).

## How to phrase inline comments

- Lead with the rule, not the explanation. Example:
  > Generated file edit. `apis/v1alpha1/zz_generated.deepcopy.go` is
  > rebuilt by `make build-controller`. See
  > [Golden Rules](https://github.com/aws-controllers-k8s/ack-dev-skills/blob/main/skills/ack-dev/SKILL.md#golden-rules).

- For codegen-config violations, suggest the exact YAML stanza when
  obvious.

- Avoid stacking many inline comments on the same root cause — pick the
  most-instructive line.

## How to set `event`

| Event | When |
|---|---|
| `COMMENT` | Default. Use even when there are several findings; the maintainer decides whether to block |
| `REQUEST_CHANGES` | Only when at least one inline comment names a Severity:REQUEST_CHANGES blocker (sections A–H, J above) |
| `APPROVE` | Almost never appropriate for an automated first pass; requires `--allow-approve` |
