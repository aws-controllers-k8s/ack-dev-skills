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

### Phase 3: Completion

Report to the user:

1. **Result**: Approved by Reviewer, or unresolved issues remaining
2. **Plan summary**: Key decisions (primary key, tagging approach, hooks needed)
3. **Files created/modified**: Grouped by category (config, hooks, tests, generated)
4. **Build status**: Controller compiles, unit tests pass
5. **Next steps**:
   - Run e2e tests against AWS (not done by the agent)
   - Squash commits
   - Open PR (or push to existing branch)

## Claude Code Execution

When running in Claude Code, each "delegate" maps to spawning the corresponding subagent:

- **Planner** → spawn `ack-planner` subagent with plan task
- **Implementer** → spawn `ack-implementer` subagent with plan or feedback
- **Reviewer** → spawn `ack-reviewer` subagent with plan + summary

The main session holds the loop state and passes structured documents between subagents.

## Single-Context Execution (Kiro / Other Tools)

When running in a tool without subagent support:

1. Read `roles/planner.md`, execute the Planner methodology, produce the plan
2. Read `roles/implementer.md`, execute with the plan as input
3. Read `roles/reviewer.md`, review your own implementation output
4. If REVISE: re-read `roles/implementer.md` and address the feedback
5. Repeat until APPROVE or max iterations

The role SOPs enforce boundaries through instruction ("do not write code", "do not modify files") even without process isolation.
