# Review Output Schema

The Reviewer must produce a document with exactly this structure.

---

## Decision: APPROVE | REVISE

## Summary

1-3 sentence overall assessment of the implementation quality.

## Findings

### MUST FIX

Items that block approval. Each must include a specific fix instruction.

Format:
```
1. [Category: generator.yaml | hooks | tests | build | plan-compliance]
   - File: <path>
   - Issue: <specific description of what is wrong>
   - Fix: <specific instruction for what to change>
```

### SHOULD FIX

Strong recommendations that don't block approval but would improve quality.

Format:
```
1. [Category]
   - File: <path>
   - Issue: <description>
   - Suggestion: <how to fix>
```

### SUGGESTIONS

Optional improvements. The Implementer may skip these if non-trivial.

Format:
```
1. [Category]
   - Description: <suggestion>
```

## Checklist Results

Reproduce the full review checklist with pass/fail for each item:

### generator.yaml
- [ ] Resource removed from ignore list
- [ ] CRUD operations properly configured
- [ ] Primary key identified with is_primary_key: true
- [ ] Field renames cover ALL operations where field appears
- [ ] Immutable fields marked
- [ ] Error codes match actual AWS API behavior
- [ ] Tags configuration correct
- [ ] Wrapper field paths correct (if applicable)
- [ ] Cross-resource references correct (same-service vs cross-service)
- [ ] Only non-default fields configured

### Generated Code
- [ ] CRD fields match plan expectations
- [ ] Spec vs Status placement correct
- [ ] No unexpected fields
- [ ] Helm chart updated

### Custom Hooks (if applicable)
- [ ] Correct hook variable names per hook point
- [ ] Uses renamed field names (not original AWS names)
- [ ] No nil pointer risks
- [ ] Logic matches plan requirements
- [ ] Hooks referenced in generator.yaml

### Build
- [ ] Controller compiles cleanly
- [ ] Unit tests pass

### E2E Tests
- [ ] Test file exists
- [ ] Resource template exists
- [ ] Covers Create, Read, Update (if applicable), Delete
- [ ] Synced condition verified
- [ ] Dual verification (CR state + AWS API state)
- [ ] Appropriate wait/timeout for resource provisioning

### Plan Compliance
- [ ] All plan items addressed
- [ ] Deviations justified

## Iteration

- **Current iteration:** N of max 3
- **Trend:** Improving | Stable | Regressing
- **Recommendation:** If iteration 3 and still REVISE, state what remains and recommend escalation to human review.
