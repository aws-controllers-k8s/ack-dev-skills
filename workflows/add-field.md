# Workflow: Add Field

Add a new field to an existing AWS resource in an ACK service controller. Orchestrates a Planner → Implementer → Reviewer loop with iterative refinement.

This is the field-scoped counterpart to `workflows/add-resource.md`. The resource already exists; this workflow adds a single field to it (Spec or Status). It uses:
- a dedicated **field planner** (`roles/field-planner.md` / `ack-field-planner`), since field research diverges most from resource research; and
- the **generic implementer and reviewer** agents (`ack-implementer`, `ack-reviewer`). Their SOPs are task-agnostic and instruct them to read the field-specific reference (`field-addition.md`) when the task is a single-field addition — so no dedicated field implementer/reviewer agent is needed. Each delegation prompt below reminds them this is a field addition and to consult that reference.

## Trigger

Invoked when asked to add a field to an existing resource in an ACK controller. Requires:
- **SERVICE**: AWS service name (e.g., `backup`, `ecr`)
- **RESOURCE**: Existing resource name (e.g., `BackupVault`, `Repository`)
- **FIELD**: The field to add (e.g., `EncryptionKeyArn`, `ImageScanningConfiguration`)
- **CONTROLLER_DIR**: Path to the service controller repository
- **CODEGEN_DIR**: Path to the code-generator repository

## Workflow

### Phase 1: Planning

Delegate to the **Field Planner** role (`roles/field-planner.md`):

> Execute the Field Planner role for SERVICE={SERVICE} RESOURCE={RESOURCE} FIELD={FIELD}.
> CONTROLLER_DIR={CONTROLLER_DIR} CODEGEN_DIR={CODEGEN_DIR}.
> Produce the plan following roles/schemas/field-plan-output.md.

Store the returned plan document.

### Phase 1.5: Plan Review

Delegate to the **Reviewer** (`ack-reviewer`) with `Review type: plan-review`:

> Review the plan document for SERVICE={SERVICE} RESOURCE={RESOURCE} FIELD={FIELD}.
> This is a single-field addition — read and apply `field-addition.md` alongside the Reviewer SOP.
> CONTROLLER_DIR={CONTROLLER_DIR} CODEGEN_DIR={CODEGEN_DIR}.
> Review type: plan-review. Verify the field exists in the resolved SDK model, Spec/Status
> classification, renames cover all operations, reference handling, and custom code necessity.

IF reviewer decision == APPROVE:
  Proceed to Phase 2.

ELSE (REVISE):
  Pass reviewer feedback back to the Planner for a revised plan (maximum 1 re-plan attempt).
  Use the revised plan for Phase 2.

### Phase 2: Implementation Loop

Maximum **4 total iterations** (1 initial implementation + up to 3 review cycles).

```
iteration = 0

LOOP:
  iteration += 1

  IF iteration == 1:
    Delegate to the Implementer (ack-implementer):
      Instruction: this is a single-field addition — read and follow `field-addition.md` alongside the Implementer SOP
      Input: plan document
      Context: SERVICE, RESOURCE, FIELD, CONTROLLER_DIR, CODEGEN_DIR

  ELSE:
    Delegate to the Implementer (ack-implementer):
      Instruction: this is a single-field addition — read and follow `field-addition.md` alongside the Implementer SOP
      Input: reviewer feedback + original plan (for reference)
      Context: SERVICE, RESOURCE, FIELD, CONTROLLER_DIR, CODEGEN_DIR

  Store the Implementer's summary.

  Delegate to the Reviewer (ack-reviewer), Review type: implementation-review:
    Instruction: this is a single-field addition — read and apply `field-addition.md` alongside the Reviewer SOP
    Input: plan document + implementation summary
    Context: CONTROLLER_DIR, iteration count

  IF reviewer decision == APPROVE:
    BREAK → proceed to Phase 3

  ELSE IF iteration >= 4:
    BREAK → report unresolved issues to user

  ELSE:
    Store reviewer feedback → continue LOOP
```

### Phase 3: E2E Testing

After the reviewer approves (or max iterations reached with a compilable result), run the e2e tests. For a field addition the test is an **extension of the resource's existing e2e test** — it should set the new field on create and, if the field is mutable, update it and re-verify.

1. Ensure `test_config.yaml` exists in the test-infra directory (`CONTROLLER_DIR/../test-infra/`). If not, copy from `test_config.example.yaml` and configure:
   - `aws.assumed_role_arn` — the developer's test role
   - `tests.methods` — filter to the resource's test (e.g., `- test_<resource>`)
   - `debug.enabled: true`
   - `debug.dump_controller_logs: true`

2. Set `ARTIFACTS` environment variable and run tests **in the background** (they take 10–30+ minutes):
   ```bash
   export ARTIFACTS=/tmp/ack-test-logs
   cd CONTROLLER_DIR/../test-infra && make kind-test SERVICE=<service>
   ```
   Do not poll or sleep — wait for the completion notification.

3. When tests complete:
   - If **PASS**: proceed to Phase 4
   - If **SKIPPED**: Treat skipped tests as failures if they were added/modified by the Implementer in this workflow. Tests that skip due to missing environment variables or unmet preconditions indicate the test was written in a way that cannot actually execute in the test harness. Spawn `ack-implementer` (with the field-addition instruction) explaining that skipped tests are not acceptable — tests must use the bootstrap system (`service_bootstrap.py` / `bootstrap_resources.py`) or create resources in fixtures, following the patterns of existing tests in the controller. Do not use environment variables to gate test execution.
   - If **FAIL**: read the test output and controller logs (`$ARTIFACTS/`). A common field-specific cause is the boto3 assertion not seeing the new field (`KeyError`) — fix by bumping the test-infra pin in `test/e2e/requirements.txt` to a commit with a newer boto3 (`acktest @ git+https://github.com/aws-controllers-k8s/test-infra.git@<latest-commit-hash>`). For other failures, spawn `ack-implementer` (with the field-addition instruction) with the failure details to fix the issue, then re-run tests. Maximum 2 fix attempts before escalating to the user.

See `skills/ack-dev/references/running-e2e-tests.md` for full test-infra configuration details and `skills/ack-dev/references/testing.md` for the boto3/test-infra pin guidance.

### Phase 4: Completion

Report to the user:

1. **Result**: Approved by Reviewer, e2e test status
2. **Plan summary**: Key decisions (Spec vs Status, mutable/immutable, renames, SDK version bump if any, references)
3. **Files created/modified**: Grouped by category (config, hooks, tests, generated)
4. **Build status**: Controller compiles, unit tests pass
5. **E2E test status**: Pass/fail, which tests ran, any remaining failures
6. **Next steps**:
   - Squash commits
   - Open PR (or push to existing branch), with the description written per [pr-description.md](../skills/ack-dev/references/pr-description.md) — new fields warrant a minor semver bump

## Claude Code Execution

When running in Claude Code, each "delegate" maps to spawning the corresponding subagent. Only the planner is field-specific; the implementer and reviewer are the generic agents, told in their prompt that this is a field addition so they read `field-addition.md`:

- **Field Planner** → spawn `ack-field-planner` subagent with the field plan task
- **Reviewer (plan review)** → spawn `ack-reviewer` subagent with plan + `Review type: plan-review` + the field-addition instruction
- **Implementer** → spawn `ack-implementer` subagent with plan or feedback + the field-addition instruction
- **Reviewer (implementation review)** → spawn `ack-reviewer` subagent with plan + summary + `Review type: implementation-review` + the field-addition instruction

The main session holds the loop state and passes structured documents between subagents.

## Single-Context Execution (Kiro / Other Tools)

When running in a tool without subagent support:

1. Read `roles/field-planner.md`, execute the field-planning methodology, produce the plan per `roles/schemas/field-plan-output.md`
2. Read `roles/reviewer.md` + `references/field-addition.md` (Plan Review), execute against the plan
3. If REVISE: re-read `roles/field-planner.md` and revise the plan (max 1 re-plan)
4. Read `roles/implementer.md` + `references/field-addition.md`, execute with the plan as input
5. Read `roles/reviewer.md` + `references/field-addition.md` (Implementation Review), review your own implementation output
6. If REVISE: re-read `roles/implementer.md` + `references/field-addition.md` and address the feedback
7. Repeat until APPROVE or max iterations

The role SOPs enforce boundaries through instruction ("do not write code", "do not modify files") even without process isolation.
