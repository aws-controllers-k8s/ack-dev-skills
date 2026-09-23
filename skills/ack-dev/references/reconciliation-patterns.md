# Delta, Comparison, and Reconciliation Patterns

Distilled from PR review comments across ACK repos. Covers the most common issues reviewers flag around delta handling, ReadOne completeness, conditions, and reconciliation loops.

## Contents
- ReadOne Must Return Complete State
- Delta and Unordered Arrays
- Custom Delta Handling
- Conditions: Terminal vs Transient
- Reconciliation Loops (Constant Requeue)
- Hook Best Practices

## ReadOne Must Return Complete State

**This is the #1 pattern reviewers enforce.** The reconciler compares `desired.Spec` vs `latest.Spec` to decide whether to call Update. If ReadOne doesn't populate a Spec field, the reconciler sees a diff and triggers unnecessary updates.

**Pattern:** Use `sdk_read_one_post_set_output` hook to populate Spec fields from additional API calls.

```go
// templates/hooks/replication_group/sdk_read_one_post_set_output.go.tpl
// Populate EngineVersion from DescribeCacheClusters since
// DescribeReplicationGroups doesn't return it directly
engineVersion, err := rm.getEngineVersion(ctx, ko)
if err != nil {
    return nil, err
}
ko.Spec.EngineVersion = engineVersion
```

**Why (elasticache-controller PR#20, jaypipes):** "ReadOne should return the latest observed representation of the resource, and if the way to determine the latest EngineVersion is to make some additional calls to DescribeCacheCluster, then that's what the `sdk_read_one_post_set_output` hook point is good for."

**Best practice (ec2-controller PR#105, jaypipes):** Isolate the "getter" method to just return the value, then have the hook do the setting:

```go
// In hooks.go - getter method
func (rm *resourceManager) getEngineVersion(ctx context.Context, ko *resource) (*string, error) {
    // Make API call, return value
}

// In template - hook sets the value
ko.Spec.EngineVersion = engineVersion
```

Don't set Spec/Status values from within internal helper functions. Keep the hook as the single place that modifies the resource.

## Delta and Unordered Arrays

**Problem:** Generated delta code uses `reflect.DeepEqual` which is order-sensitive. Tags and other list fields returned by AWS may be in different order than the desired spec.

**Symptom:** Controller constantly reconciles even when nothing changed, because `[{Key:A, Value:1}, {Key:B, Value:2}]` ≠ `[{Key:B, Value:2}, {Key:A, Value:1}]`.

**Solution (ec2-controller PR#106, a-hilaly):** "The problem here is more related to the generated code in `delta.go`/`rm.compareResources` — the generated code uses `DeepEqual` from the `reflect` library which takes into consideration the order of the elements."

For tags specifically, the runtime handles comparison. For other list fields, use `compare.is_ignored` + a custom delta function:

```yaml
# generator.yaml - skip generated comparison for this field
resources:
  Table:
    fields:
      KeySchema:
        compare:
          is_ignored: true
```

Then write a custom comparison function:

```go
// pkg/resource/table/delta_util.go
func equalKeySchemaArrays(a, b []*svcapitypes.KeySchemaElement) bool {
    // Sort both slices by a stable key before comparing
    sort.Slice(a, func(i, j int) bool { return *a[i].AttributeName < *a[j].AttributeName })
    sort.Slice(b, func(i, j int) bool { return *b[i].AttributeName < *b[j].AttributeName })
    return reflect.DeepEqual(a, b)
}
```

**From dynamodb-controller PR#30 (a-hilaly):** "`is_immutable` doesn't ignore the field comparison in the generated delta function. I added `is_ignored: true` because the DynamoDB control plane sorts the KeySchema array, causing the controller to reconcile forever."

**Don't confuse `is_immutable` with `is_ignored`:** `is_immutable` prevents updates but still compares. `compare.is_ignored` skips comparison entirely (you handle it yourself).

## Custom Delta Handling

When the generated delta isn't sufficient, use `delta_pre_compare` or `delta_post_compare` hooks:

```yaml
resources:
  ReplicationGroup:
    hooks:
      delta_pre_compare:
        code: customPreCompare(delta, a, b)
```

**Common cases:**
- **Enum vs bool mapping:** API returns `"enabled"/"disabled"` string but Spec has `*bool`. Don't force the string into a bool — compare against the full Status value instead.
- **Nested fields from different APIs:** When a Spec field's latest value comes from a different API than ReadOne, populate it in `sdk_read_one_post_set_output` so delta works naturally.
- **Fields managed by parent resources:** (e.g., RDS DBInstance fields inherited from DBCluster) — ignore these fields in delta when the parent is set.

## Conditions: Terminal vs Transient

**Terminal condition (`ACK.Terminal`):** Set ONLY for unrecoverable errors where the user must change the spec.

```go
// CORRECT: Bad spec, user must fix
if awsErr.Code() == "InvalidParameterValueException" {
    return nil, ackerr.NewTerminalError(err)
}

// WRONG: Quota exceeded is transient, don't make terminal
if awsErr.Code() == "LimitExceededException" {
    return nil, err  // Just return error, will requeue
}
```

**Synced condition (`ACK.ResourceSynced`):** Set to False when the resource is still being created/modified by AWS.

```go
// In sdk_create_post_set_output or sdk_update_post_set_output
if ko.Status.State != nil && *ko.Status.State != "ACTIVE" {
    ackcondition.SetSynced(ko, corev1.ConditionFalse, nil, nil)
} else {
    ackcondition.SetSynced(ko, corev1.ConditionTrue, nil, nil)
}
```

**IsSynced pattern:** For resources with async operations, implement `IsSynced()` to control requeue:

```go
func (rm *resourceManager) IsSynced(ctx context.Context, r acktypes.AWSResource) (bool, error) {
    ko := rm.concreteResource(r).ko
    if ko.Status.Status != nil && *ko.Status.Status != "available" {
        return false, nil
    }
    return true, nil
}
```

## Reconciliation Loops (Constant Requeue)

**Symptom:** Controller logs show "desired resource state has changed" repeatedly with the same diff.

**Common causes:**
1. **ReadOne doesn't populate a Spec field** → reconciler sees diff → calls Update → Update doesn't change it → loop
2. **Unordered array comparison** → tags/lists in different order → false diff
3. **Fields inherited from parent resource** → DBInstance inherits from DBCluster, controller tries to update directly
4. **API returns different format** → e.g., JSON policy with different whitespace/ordering

**Fix for cause 1:** Add `sdk_read_one_post_set_output` hook
**Fix for cause 2:** Custom delta comparison
**Fix for cause 3:** Ignore fields conditionally in hooks when parent is set
**Fix for cause 4:** Normalize before comparison (e.g., `is_iam_policy` field config for semantic JSON comparison)

## Async Resource Lifecycle

Many AWS resources have async operations (Creating → Created, Deleting → DeleteFailed, etc.). These require special handling.

**Pattern (sagemaker-controller PR#52):**

1. **Don't call delete during transitional states.** If the resource is Creating or Deleting, requeue instead of calling the AWS delete API:
```go
// sdk_delete_pre_build_request hook
if ko.Status.Status != nil {
    status := *ko.Status.Status
    if status == "Creating" || status == "Deleting" {
        return nil, requeueWaitWhileDeleting
    }
}
```

2. **After delete, re-read to get final status.** Call sdkFind after delete to patch the resource with "Deleting" or "DeleteFailed" status.

3. **Set Synced=False during transitions.** Any non-terminal state should have `ACK.ResourceSynced = False`:
```go
if status != "Created" && status != "Active" && status != "InService" {
    ackcondition.SetSynced(ko, corev1.ConditionFalse, nil, nil)
}
```

**Requeue after async updates (dynamodb-controller PR#30, eks-controller pattern):**
```go
// After triggering an async update, requeue to check status
return &resource{ko}, requeueWaitUntilCanModify(15 * time.Second)
```

## Nil Guards in Hooks

**The #1 cause of controller panics.** Every field access in hook code must check for nil.

```go
// WRONG - panics if SSESpecification is nil
if *r.ko.Spec.SSESpecification.Enabled {

// CORRECT
if r.ko.Spec.SSESpecification != nil && r.ko.Spec.SSESpecification.Enabled != nil {
```

**For slices, use `len()` not nil check (codegen PR#378, a-hilaly):**
```go
// WRONG - unreliable for slices
if resourceConfig.Print.AdditionalColumns != nil {

// CORRECT
if len(resourceConfig.Print.AdditionalColumns) > 0 {
```

## Avoid custom_update_operation

Reviewers consistently push back on custom update methods. Use hooks instead.

**From eventbridge-controller PR#15 (jaypipes):** "This doesn't need to be a custom update method... you could save yourself some hassle by using the standard generated update code paths with a couple hooks."

**From cloudtrail-controller PR#6 (jaypipes):** "All of this would be auto-generated if we did not use a custom update method."

**Pattern for tag-only updates with hooks:**
```go
// sdk_update_pre_build_request.go.tpl
if delta.DifferentAt("Spec.Tags") {
    err = rm.syncTags(ctx, latest, desired)
    if err != nil {
        return nil, err
    }
}
if !delta.DifferentExcept("Spec.Tags") {
    return desired, nil  // Only tags changed, skip the main update
}
```

## Server-Side Defaults vs Overrides

**Server-side defaults:** AWS sets a value when the user doesn't provide one (e.g., encryption type defaults to AES256). Use late initialization to populate these in Spec.

**Server-side overrides:** AWS modifies a user-provided value (e.g., adds system tags, normalizes JSON). These are trickier — you need custom comparison logic to avoid reconciliation loops.

**Pattern (applicationautoscaling-controller PR#12):** "Set the server defaults for values that are null and let the comparison happen like normal. This handles the case where the user initially sets a field to true and deletes it from spec thinking it will take the default value."

```go
// In sdk_read_one_post_set_output hook
if ko.Spec.SuspendedState == nil {
    ko.Spec.SuspendedState = &svcapitypes.SuspendedState{
        DynamicScalingInSuspended:  aws.Bool(false),
        DynamicScalingOutSuspended: aws.Bool(false),
        ScheduledScalingSuspended:  aws.Bool(false),
    }
}
```

## Resources Without Update API

Some resources have no Update API (e.g., BackupSelection, some SageMaker resources). Options:

1. **Delete and recreate:** Set `is_immutable: true` on all Spec fields. User must delete and recreate to change anything.
2. **Return terminal error on update attempt:** In `sdk_update_pre_build_request`, return `ackerr.NewTerminalError` with a message explaining updates aren't supported.
3. **Tag-only updates:** If the resource supports TagResource but no other updates, handle tags in a hook and skip the main update path.

**From emrcontainers-controller PR#92 (knottnt):** For resources where tags can only be updated in certain states, consider ignoring tag changes rather than failing with a Terminal condition.

## Hook Best Practices

**Variable names by hook point:** See [troubleshooting.md](troubleshooting.md) "Hook Variable Names by SDK Method" for the full table. The most common bug is using `latest` in delete hooks — `latest` is the return variable in `sdkDelete`, not the input. Use `r` instead.

**Don't use custom_update_operation unless absolutely necessary.** It bypasses generated immutability checks. Prefer `sdk_update_pre_build_request` + `sdk_update_post_build_request` hooks instead.

**From iam-controller PR#42 (jaypipes):** "Because you've used a custom update method, the immutability guarantee code is no longer generated for `sdkUpdate` which means this block of code here actually violates the immutability guarantee."

**Record API calls in hooks:**
```go
rm.metrics.RecordAPICall("READ_ONE", "ListTags", err)
```

**Return updated resource from Update hooks:**
```go
// WRONG - returns nil, loses state
return nil, nil

// CORRECT - return resource with desired spec + latest status
return &resource{ko}, nil
```
