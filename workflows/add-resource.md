# Workflow: Add Resource

Add a new AWS resource to an ACK service controller. Orchestrates a Planner → Implementer → Reviewer loop with iterative refinement.

## Trigger

Invoked when asked to add a new resource to an ACK controller. Requires:
- **SERVICE**: AWS service name (e.g., `backup`, `ecr`)
- **RESOURCE**: Resource name (e.g., `BackupVault`, `Repository`)
- **CONTROLLER_DIR**: Path to the service controller repository
- **CODEGEN_DIR**: Path to the code-generator repository

## Workflow

### Phase 1: Planning

Delegate to the **Planner** role (`roles/planner.md`):

> Execute the Planner role for SERVICE={SERVICE} RESOURCE={RESOURCE}.
> CONTROLLER_DIR={CONTROLLER_DIR} CODEGEN_DIR={CODEGEN_DIR}.
> Produce the plan following roles/schemas/plan-output.md.

Store the returned plan document.

### Phase 1.5: Plan Review

Delegate to the **Reviewer** role (`roles/reviewer.md`) in plan-review mode:

> Review the plan document for SERVICE={SERVICE} RESOURCE={RESOURCE}.
> CONTROLLER_DIR={CONTROLLER_DIR} CODEGEN_DIR={CODEGEN_DIR}.
> Mode: plan-review. Verify API constraints and custom code necessity against the SDK model.

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
    Delegate to Implementer role (roles/implementer.md):
      Input: plan document
      Context: SERVICE, RESOURCE, CONTROLLER_DIR, CODEGEN_DIR

  ELSE:
    Delegate to Implementer role (roles/implementer.md):
      Input: reviewer feedback + original plan (for reference)
      Context: SERVICE, RESOURCE, CONTROLLER_DIR, CODEGEN_DIR

  Store the Implementer's summary.

  Delegate to Reviewer role (roles/reviewer.md):
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

After the reviewer approves (or max iterations reached with a compilable result), run the e2e tests.

1. Ensure `test_config.yaml` exists in the test-infra directory (`CONTROLLER_DIR/../test-infra/`). If not, copy from `test_config.example.yaml` and configure:
   - `aws.assumed_role_arn` — the developer's test role
   - `tests.methods` — filter to the new resource's tests (e.g., `- test_<resource>`)
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
   - If **SKIPPED**: Treat skipped tests as failures if they were added by the Implementer in this workflow. Tests that skip due to missing environment variables or unmet preconditions indicate the test was written in a way that cannot actually execute in the test harness. Spawn `ack-implementer` with feedback explaining that skipped tests are not acceptable — tests must use the bootstrap system (`service_bootstrap.py` / `bootstrap_resources.py`) or create resources in fixtures, following the patterns of existing tests in the controller. Do not use environment variables to gate test execution.
   - If **FAIL**: read the test output and controller logs (`$ARTIFACTS/`). Spawn `ack-implementer` with the failure details to fix the issue, then re-run tests. Maximum 2 fix attempts before escalating to the user.

See `skills/ack-dev/references/running-e2e-tests.md` for full test-infra configuration details.

### Phase 4: Completion

Report to the user:

1. **Result**: Approved by Reviewer, e2e test status
2. **Plan summary**: Key decisions (primary key, tagging approach, hooks needed)
3. **Files created/modified**: Grouped by category (config, hooks, tests, generated)
4. **Build status**: Controller compiles, unit tests pass
5. **E2E test status**: Pass/fail, which tests ran, any remaining failures
6. **Next steps**:
   - Squash commits
   - Open PR (or push to existing branch)

## Claude Code Execution

When running in Claude Code, each "delegate" maps to spawning the corresponding subagent:

- **Planner** → spawn `ack-planner` subagent with plan task
- **Reviewer (plan-review)** → spawn `ack-reviewer` subagent with plan + `Mode: plan-review`
- **Implementer** → spawn `ack-implementer` subagent with plan or feedback
- **Reviewer** → spawn `ack-reviewer` subagent with plan + summary

The main session holds the loop state and passes structured documents between subagents.

## Single-Context Execution (Kiro / Other Tools)

When running in a tool without subagent support:

1. Read `roles/planner.md`, execute the Planner methodology, produce the plan
2. Read `roles/reviewer.md`, execute in plan-review mode against the plan
3. If REVISE: re-read `roles/planner.md` and revise the plan (max 1 re-plan)
4. Read `roles/implementer.md`, execute with the plan as input
5. Read `roles/reviewer.md`, review your own implementation output
6. If REVISE: re-read `roles/implementer.md` and address the feedback
7. Repeat until APPROVE or max iterations

The role SOPs enforce boundaries through instruction ("do not write code", "do not modify files") even without process isolation.
