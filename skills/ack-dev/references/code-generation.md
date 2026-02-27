# Code Generation Deep Dive

## How It Works

```
AWS API Model → ack-generate → Generated Code
     ↓              ↓              ↓
  service.json  generator.yaml  CRDs + Go types
```

The code generator reads AWS API models and generates:
- Kubernetes CRDs
- Go types
- Controller logic
- SDK integration

## Customization Patterns

- **Skip fields**: Add to `ignore.field_paths` in generator.yaml
- **Rename fields**: Use `renames.operations` in generator.yaml
- **Mark immutable**: Set `is_immutable: true`
- **Add validation**: Use kubebuilder markers in custom types
- **Custom conversion**: Implement in hooks

## OriginalShapeName Awareness

The code-generator applies "stutter removal" to shape names (e.g., `BackupBackupPlanInput` -> `BackupPlanInput`) for cleaner CRD types. However, when generating code that constructs SDK types, you must use the original AWS SDK shape name.

The `OriginalShapeName` field on shapes stores the pre-rename name. In `varEmptyConstructorSDKType()`, always check `shape.OriginalShapeName` when building SDK type references:

```go
if shape.Type == "structure" && shape.OriginalShapeName != "" {
    goType = "svcsdktypes." + shape.OriginalShapeName
}
```

Without this, generated code would reference non-existent SDK types when stutter removal has renamed them.

This applies to map value types too. When a map's values are structures, `varEmptyConstructorSDKType()` must check `shape.ValueRef.Shape.OriginalShapeName` for the value type:

```go
} else if shape.ValueRef.Shape.Type == "structure" {
    valueShapeName := shape.ValueRef.ShapeName
    if shape.ValueRef.Shape.OriginalShapeName != "" {
        valueShapeName = shape.ValueRef.Shape.OriginalShapeName
    }
    goType = "map[string]svcsdktypes." + valueShapeName
}
```

## BadDefaultsAssignment (`pkg/apiv2/remove_defaults.go`)

The AWS SDK Go v2 has a `RemoveDefaults` customization that strips default values from Smithy shapes where the default conflicts with range constraints (e.g., a default of 0 on a field with `@range(min: 1)`). This makes those fields nillable (pointers) in the generated SDK code.

ACK mirrors this in `BadDefaultsAssignment` — a map of service name → member names that need pointer treatment. If a field is in this map but ACK doesn't treat it as a pointer, you get type errors like:

> `cannot use &f9valiter.WorkerCount (value of type **int64) as *int64 value in assignment`

**Critical gotcha:** The map keys must use Go struct member names, not Smithy shape names. These can differ (e.g., Smithy shape `WorkerCounts` → Go member `WorkerCount`). To find the correct name:
1. Check the SDK source: `codegen/sdk-codegen/aws-models/<service>.json` in [aws-sdk-go-v2](https://github.com/aws/aws-sdk-go-v2)
2. Look at the generated Go types in the SDK package to confirm the member name

**Example PR:** code-generator PR #671 (fixed `WorkerCounts` → `WorkerCount` for EMR Serverless)

## Nested Response Handling (`output_wrapper_field_path`)

Some AWS APIs wrap responses in a nested object. Without configuration, the entire wrapper ends up in Status.

```yaml
operations:
  CreateResource:
    output_wrapper_field_path: ResourceName
  UpdateResource:
    output_wrapper_field_path: ResourceName
  DescribeResources:
    output_wrapper_field_path: ResourceNames  # Note: plural for list operations
```

## Nested Input Handling (`input_wrapper_field_path`)

Some AWS APIs wrap *input* fields in a nested structure. For example, AWS Backup's `CreateBackupPlan` requires a `BackupPlan` wrapper containing the actual plan fields.

Without configuration, users would need to nest fields under `spec.backupPlan.backupPlanName`. With `input_wrapper_field_path`, the wrapper's fields are flattened directly into the CRD Spec.

```yaml
operations:
  CreateBackupPlan:
    input_wrapper_field_path: BackupPlan
    output_wrapper_field_path: BackupPlan
  UpdateBackupPlan:
    input_wrapper_field_path: BackupPlan
    output_wrapper_field_path: BackupPlan
  GetBackupPlan:
    output_wrapper_field_path: BackupPlan
```

How it works internally:
- During CRD construction (`model.go`), the wrapper's member fields are added to Spec instead of the wrapper itself. Fields outside the wrapper are excluded (consistent with `output_wrapper_field_path` behavior).
- During code generation (`set_sdk.go`), a wrapper struct variable (`fw`) is created, populated from Spec fields, then assigned to the input shape's wrapper field (e.g., `res.BackupPlan = fw`).
- The `getWrapperShape` function in `crd.go` handles both input and output unwrapping, including list-of-structure wrappers.

Current limitations:
- Only structure wrappers are supported at the top level in `model.go` during CRD construction
- Nested paths (e.g., `a.b.c` where `b` is a list) could be extended in a future PR
- The code-generation side (`crd.go`) already handles list types via `getWrapperShape`

**Example PRs:**
- ECR RepositoryCreationTemplate with output_wrapper_field_path: PR #142 (ecr-controller)
- Backup BackupPlan with input_wrapper_field_path: PR #657 (code-generator)
