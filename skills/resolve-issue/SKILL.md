---
name: resolve-issue
description: >
  Triage and work on an ACK community issue end-to-end. Fetches the issue,
  ensures the controller repo is cloned/forked, classifies and labels it,
  then executes the appropriate workflow (bug fix, new resource, new field,
  feature investigation, unknown investigation) inline.
argument-hint: issue-number
arguments: [issue]
allowed-tools:
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git checkout *)
  - Bash(git branch *)
  - Bash(git add *)
  - Bash(git commit *)
  - Bash(git stash *)
  - Bash(git show *)
  - Bash(git rev-parse *)
  - Bash(git -C * status *)
  - Bash(git -C * diff *)
  - Bash(git -C * log *)
  - Bash(git -C * checkout *)
  - Bash(git -C * branch *)
  - Bash(git -C * add *)
  - Bash(git -C * commit *)
  - Bash(git -C * stash *)
  - Bash(git -C * show *)
  - Bash(git -C * rev-parse *)
  - Bash(bash *)
  - Bash(go build *)
  - Bash(go test *)
  - Bash(find *)
  - Bash(grep *)
  - Bash(make *)
  - Bash(ls *)
  - Bash(mkdir *)
  - Bash(gh issue view *)
  - Bash(gh issue list *)
  - Bash(gh issue edit *)
  - Bash(gh pr view *)
  - Bash(gh pr list *)
  - Bash(gh pr diff *)
  - Bash(gh search *)
  - Bash(gh api repos/*/pulls/*/comments*)
  - Bash(gh api repos/*/issues/*/comments*)
  - Bash(gh api user*)
  - Bash(gh label create *)
  - Read
  - Edit
  - Write
---

# Resolve Issue — ACK Unified Workflow

You take an ACK community GitHub issue and drive it to resolution — all in one pass, no subagents.

## Environment Setup

Detect the workspace root automatically. The workspace is the parent directory containing multiple ACK repos (code-generator, runtime, *-controller, etc.).

```bash
# Auto-detect workspace: walk up from cwd until we find code-generator or a *-controller dir
ACK_WORKSPACE="$(cd .. && pwd)"
if [[ ! -d "${ACK_WORKSPACE}/code-generator" ]]; then
  ACK_WORKSPACE="$(pwd)"
fi
```

Detect the current GitHub user:
```bash
GH_USER="$(gh api user --jq .login)"
```

Scripts are located relative to this skill file at `scripts/`.

## Shared Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `ensure-repo.sh` | Clone/fork/pull a controller repo | `bash scripts/ensure-repo.sh <name>-controller [github-user] [workspace-path]` |
| `regenerate.sh` | Run code generation | `bash scripts/regenerate.sh <service> [workspace-path]` |
| `check-breaking-changes.sh` | CRD compatibility check | `bash scripts/check-breaking-changes.sh <service> [workspace-path]` |
| `run-tests.sh` | Run unit tests | `bash scripts/run-tests.sh <service> [workspace-path]` |

All scripts auto-detect `ACK_WORKSPACE` from `$PWD` if not passed explicitly.

---

## Phase 1: Triage

### Step 1: Fetch and understand the issue

```
gh issue view $issue --repo aws-controllers-k8s/community --json title,body,labels,comments
```

Extract:
- **Title and body** — what is being requested or reported?
- **Comments** — any additional context, reproduction steps, or clarification from maintainers
- **Existing labels** — check for `kind/*` and `service/*` labels
- **Target controller** — from `service/<name>` label or by reading the issue body
- **Resource** — mentioned in title/body

If the issue references multiple services, report to user and ask which to focus on.

### Step 1.5: Check for out-of-scope (data plane) requests

ACK only manages AWS **control plane** resources. If the issue requests **data plane** functionality (reading/writing objects in S3, invoking Lambda, sending SQS messages, querying DynamoDB items, etc.), it is **out of scope**.

**Draft a concise response** (2-3 sentences max) explaining why. Present to user for review. STOP.

### Step 2: Classify and label

| Classification | Label | Criteria |
|---------------|-------|----------|
| Bug report | `kind/bug` | Something is broken, regression, unexpected behavior, panic, drift |
| New resource request | `kind/new-resource` | "Add support for X", "New resource: X" |
| New field on existing resource | `kind/new-field` | "Add field X to resource Y", field missing from Spec/Status |
| Enhancement | `kind/feature` | Improvement to existing behavior, new capability |
| Documentation | `kind/documentation` | Docs missing or incorrect |
| New service controller | `kind/new-service` | Request for an entirely new controller |
| Needs investigation | `kind/needs-investigation` | Unclear what the right fix is |

Only apply labels automatically if >90% confident. Otherwise ASK the user.

If no `kind/*` label and confident: `gh issue edit $issue --repo aws-controllers-k8s/community --add-label "<label>"`

If existing label disagrees with your classification: explain why and ASK before changing.

### Step 3: Ensure the controller repo is cloned and forked

```
bash scripts/ensure-repo.sh <name>-controller
```

### Step 4: Route to the appropriate workflow below

- `kind/bug` → Phase 2A
- `kind/new-resource` → Phase 2B
- `kind/new-field` → Phase 2C
- `kind/feature` → Phase 2D
- `kind/needs-investigation` → Phase 2E
- `kind/new-service` → Tell user: "No automated workflow for new service controllers yet." STOP.
- `kind/documentation` → Draft concise response acknowledging docs gap. Present to user. STOP.

---

## Phase 2A: Fix a Bug

### A1: Search for prior art

```
gh issue list --repo aws-controllers-k8s/community --state closed --label "kind/bug" --search "<keywords>" --limit 10 --json number,title,closedAt
```

For promising matches, find the linked PR and read the diff:
```
gh pr diff <number> --repo aws-controllers-k8s/<controller>
```

### A2: Classify the symptom

| Pattern | Symptom | Likely Fix |
|---------|---------|------------|
| Infinite reconcile | Constant diffs on same field | `is_iam_policy`, `late_initialize`, custom compare |
| Ignored delta | Field change not detected | Missing `delta_pre_compare` hook |
| Update API error | Unchanged field causes error | `sdk_update_post_build_request` hook to nil unchanged fields |
| Nil pointer panic | Controller crash | Add nil checks in hooks |
| Wrong resource from ReadMany | Adopts unrelated resources | `list_operation.match_fields` |
| Tags not updating | Tags stuck after creation | Fix `ensure_tags` hook |
| Adoption failure | "Resource not found" | `is_arn_primary_key`, guard status checks |
| Deletion not working | AWS resource persists | `sdk_delete_post_request` hook |
| Orphaned resource | Name change creates new resource | `is_immutable: true` |
| Custom update broken | Updates have no effect | Replace with generated update + hooks |

If the bug does NOT match a known pattern, present root-cause analysis and ASK THE USER.

### A3: Root cause in code

Investigate:
1. `generator.yaml` — resource configuration
2. `pkg/resource/<resource>/delta.go` — field comparison
3. `pkg/resource/<resource>/sdk.go` — CRUD field mappings
4. `templates/hooks/<resource>/` — template hooks
5. `pkg/resource/<resource>/hooks.go` — custom hooks
6. AWS SDK model at `~/go/pkg/mod/github.com/aws/aws-sdk-go-v2/service/<name>@<version>/api_op_*.go`

### A4: Implement the fix

1. Create feature branch: `git checkout -b fix/<short-description>`
2. Prefer `generator.yaml` changes over custom code
3. If hooks needed, prefer `.go.tpl` templates over `hooks.go`
4. For server-defaulted fields, use `late_initialize` with `skip_incomplete_check: {}`
5. NEVER edit files marked `// Code generated by ack-generate. DO NOT EDIT.`

### A5: Regenerate and validate

If you changed `generator.yaml` or any `.go.tpl` file:
```
bash scripts/regenerate.sh <service>
bash scripts/check-breaking-changes.sh <service>
```

If `check-breaking-changes.sh` exits non-zero: STOP, revert, inform user.

### A6: Check sibling resources

Scan other resources in the same controller for the same bug pattern. Fix all instances in the same branch.

### A7: Test

```
bash scripts/run-tests.sh <service>
```

### A8: Commit

```
fix: <subject line>

<1-2 sentences: root cause and how the fix works.>

Resolves aws-controllers-k8s/community#<issue-number>
```

---

## Phase 2B: Add a New Resource

### B1: Feasibility check

ACK infers resources from `Create*` operations. Check the SDK:
```
grep 'aws-sdk-go-v2/service/<name>' <controller-repo>/go.mod
ls ~/go/pkg/mod/github.com/aws/aws-sdk-go-v2/service/<name>@<version>/api_op_*.go
```

**Standalone CRD — ALL must be true:**
1. Has `Create<Thing>` (NOT `Put<Thing>`)
2. Has `Delete<Thing>` (independent lifecycle)
3. Has its own identity (ARN, Name/ID)
4. Has meaningful independent state

**Field on parent — ANY is true:**
1. Uses `Put<Thing>`/`Get<Thing>` instead of `Create<Thing>`
2. Has `Create<Thing>` but no independent identity
3. Is a configuration toggle on a parent

**Not supported:** Data plane ops, no CRUD API, read-only

If field on parent: STOP, explain, suggest kind/new-field.
If not supported: STOP, explain why.
If ambiguous: STOP, present operations, ASK.

### B2: Investigate the AWS API

For each CRUD operation (`api_op_*.go`), note:
- Required vs optional fields on Create
- Spec fields (Create input) vs Status fields (Create output only)
- Whether Update uses same field names as Create (renames needed?)
- Extra fields from Describe (need `from.operation` + `is_read_only`)
- State machine enums → `synced.when`
- Tag support → `tags.ignore: true` if none
- Non-standard patterns (parent ARN, composite keys, non-standard 404)

### B3: Check current controller state

1. Is resource in `ignore.resource_names`?
2. Does resource name appear in `apis/v1alpha1/types.go` as nested struct?
3. What patterns do existing resources use?

### B4: Create feature branch

```
git checkout -b feat/add-<resource-name>
```

### B5: Configure generator.yaml

Work through this checklist:

| Question | If Yes |
|----------|--------|
| Resource in `ignore.resource_names`? | Remove it |
| Field names differ across operations? | Add `renames` for EACH operation |
| Async lifecycle states? | Add `synced.when` |
| No tag support? | Add `tags.ignore: true` |
| Fields only in Describe output? | Add `from.operation` + `is_read_only: true` |
| Depends on parent resource? | Add `references` |
| Cross-service reference? | Add `references.service_name` |
| Update needs custom logic? | Add `update_operation.custom_method_name` |
| Server sets defaults? | Add `late_initialize` with `skip_incomplete_check: {}` |
| K8s-irrelevant Create input fields? | Add to `ignore.field_paths` |
| Non-standard 404? | Add `exceptions.errors.404.code` |
| Terminal errors? | Add `exceptions.terminal_codes` |
| Immutable fields? | Mark `is_immutable: true` |
| Fields to show in kubectl get? | Add `print.name` |
| Periodic re-sync needed? | Add `reconcile.requeue_on_success_seconds` |

Present proposed changes to user and explain reasoning before applying. If ambiguous, ASK.

### B6: Generate and validate

```
bash scripts/regenerate.sh <service>
bash scripts/check-breaking-changes.sh <service>
```

If breaking: STOP, revert, inform user.

### B7: Review generated code

- `apis/v1alpha1/<resource>.go` — Spec/Status split correct?
- `pkg/resource/<resource>/sdk.go` — CRUD mappings correct?
- `pkg/resource/<resource>/delta.go` — comparison logic?
- `cmd/controller/main.go` — blank import exists?

If wrong, adjust generator.yaml and regenerate.

### B8: Add custom code (if needed)

Only when: API quirks, multi-call updates, ReadOne post-processing, custom comparison.
Templates in `templates/hooks/<resource_name>/<hook_name>.go.tpl`
Implementations in `pkg/resource/<resource_name>/hooks.go`

If you added hooks, regenerate again (B6).

### B9: Test

```
bash scripts/run-tests.sh <service>
```

### B10: Commit

```
feat: add <ResourceName> resource to <service> controller

<1-2 sentences: what the resource does, notable config choices.>

Resolves aws-controllers-k8s/community#<issue-number>
```

---

## Phase 2C: Add a New Field

### C1: Search for prior art

```
gh pr list --repo aws-controllers-k8s/<controller> --state merged --search "field" --limit 10 --json number,title
```

### C2: Investigate the AWS SDK model

```
grep 'aws-sdk-go-v2/service/<name>' <controller-repo>/go.mod
```

Check which operation returns the field:
- In Create output? (auto-mapped to Status)
- Only in Describe/Get output? (needs `from.operation`)
- In Create input? (should already be in Spec — investigate why missing)
- Computed/derived? (may need custom code)

### C3: Determine field configuration

| Scenario | Configuration |
|----------|--------------|
| Field only in Describe output | `from.operation` + `from.path` |
| Field is output-only | `is_read_only: true` |
| Field has server-set defaults | `late_initialize:` with `skip_incomplete_check: {}` |
| Show in kubectl get | `print.name: <COLUMN_NAME>` |
| Different name in another operation | Add `renames` |
| References another resource | Add `references` block |
| Immutable after creation | `is_immutable: true` |

### C4: Create feature branch

```
git checkout -b feat/add-<field>-to-<resource>
```

### C5: Update generator.yaml

Present proposed changes to user before applying.

### C6: Regenerate and validate

```
bash scripts/regenerate.sh <service>
bash scripts/check-breaking-changes.sh <service>
```

If breaking: STOP, revert, inform user.

### C7: Review generated code

- `apis/v1alpha1/<resource>.go` — field in correct location?
- `pkg/resource/<resource>/sdk.go` — mapping correct?
- `pkg/resource/<resource>/delta.go` — comparison included?

### C8: Test

```
bash scripts/run-tests.sh <service>
```

### C9: Commit

```
feat: add <FieldName> field to <Resource>

<1-2 sentences: where field comes from, how mapped, what it enables.>

Resolves aws-controllers-k8s/community#<issue-number>
```

---

## Phase 2D: Investigate a Feature Request

This is READ-ONLY. Do NOT implement.

### D1: Check scope

If request involves data plane operations → out of scope. Report and STOP.

### D2: Categorize the enhancement

- **generator.yaml option** — config alone
- **Hook logic** — custom code at a lifecycle point
- **Runtime change** — shared `runtime` repo
- **Code-generator change** — templates or logic
- **Cross-controller** — affects multiple controllers
- **Not possible** — needs fundamental design changes

### D3: Search for prior art

```
gh issue list --repo aws-controllers-k8s/community --state closed --label "kind/feature" --search "<keywords>" --limit 10 --json number,title
```

### D4: Assess feasibility

Investigate: generator.yaml, hooks, AWS SDK model, runtime repo, code-generator templates.

### D5: Report to user

**Issue:** #<number> — <title>
**Request:** <one-sentence summary>
**Feasibility:** Feasible / Partially feasible / Not feasible
**Approach:** Where the change would go, which files, similar PRs
**Effort:** Small (< 1 day) / Medium (1-3 days) / Large (> 3 days)
**Blockers:** Risks, dependencies, compatibility concerns
**Open questions:** What needs clarification

---

## Phase 2E: Investigate Unknown Issue

This is READ-ONLY unless user explicitly asks to fix.

### E1: Identify the symptom

Crash/panic? Perpetual reconcile? Not creating/updating/deleting? Wrong field value? Adoption failure? Performance? Unexpected AWS error?

### E2: Investigate the code

1. `generator.yaml`
2. `pkg/resource/<resource>/sdk.go`
3. `pkg/resource/<resource>/delta.go`
4. `templates/hooks/<resource>/`
5. `pkg/resource/<resource>/hooks.go`

### E3: Check AWS SDK model

```
grep 'aws-sdk-go-v2/service/<name>' <controller-repo>/go.mod
```

Read relevant `api_op_*.go` files.

### E4: Search for prior art

```
gh issue list --repo aws-controllers-k8s/community --state closed --search "<keywords>" --limit 10 --json number,title
```

### E5: Suggest reclassification

Is it actually a bug? → `kind/bug`
Missing field? → `kind/new-field`
Feature request? → `kind/feature`
New resource? → `kind/new-resource`
Still unclear? → keep as-is

### E6: Report to user

**Issue:** #<number> — <title>
**Symptom:** <user's perspective>
**Root cause:** <what's wrong, or "unclear — needs more info">
**Suggested reclassification:** <label> or "keep as-is"
**Proposed fix approach:** (if root cause is clear)
**What's still unclear:** Information gaps, questions for reporter

---

## Reference Files

Consult these when you need detailed context:

- [Bug Fix Patterns](../../references/bug-fix-patterns.md) — 10 common root causes and their fixes (infinite reconcile, nil panics, orphaned resources, etc.)
- [generator.yaml Reference](../../references/generator-yaml-reference.md) — All resource-level and field-level options, hooks, and common gotchas
- [New Resource Checklist](../../references/new-resource-checklist.md) — Feasibility checks, API investigation steps, configuration decision table

---

## Rules

- Do NOT create PRs, issues, or comments on GitHub (labeling via `gh issue edit --add-label` IS allowed)
- Do NOT push to remote
- Do NOT modify git config
- Do NOT use --no-verify or --force flags
- NEVER edit files marked `// Code generated by ack-generate. DO NOT EDIT.`
- When uncertain about classification or approach, ASK THE USER
- If multiple valid approaches exist, ASK THE USER
- Present generator.yaml changes for review before applying
- If the issue is already fixed, draft a concise response (2-3 sentences) with the PR/release link. Present to user. STOP.
