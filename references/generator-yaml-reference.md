# generator.yaml Reference

> **NEVER modify generated files directly.** All changes to controller behavior go through `generator.yaml`, hook templates (`.go.tpl`), or `hooks.go`. Files in `apis/`, `pkg/resource/*/sdk.go`, `pkg/resource/*/delta.go`, `config/crd/`, `config/rbac/`, `helm/`, and `cmd/controller/main.go` are regenerated and any manual edits will be lost.

Source: `code-generator/pkg/config/` — `config.go`, `resource.go`, `field.go`, `operation.go`

---

## Top-Level Config

```yaml
resources: {}            # Map of ResourceName → ResourceConfig
operations: {}           # Map of OperationName → OperationConfig
ignore:                  # What to skip during generation
  operations: []         # Operation IDs to ignore
  resource_names: []     # Resource names to ignore
  shape_names: []        # Shape names to ignore
  field_paths: []        # "<ShapeName>.<FieldName>" paths to ignore
empty_shapes: []         # Shapes that should be treated as empty structs
sdk_names:               # Override SDK package/interface names
  model_name: ""         # Model directory name (e.g., "opensearch")
  package_name: ""       # Go package name (e.g., "docdb")
  client_interface: ""   # Interface name (e.g., "PipesAPI")
  client_struct: ""      # Client struct name (e.g., "Pipes")
controller_name: ""      # Override controller name (e.g., "documentdb" for docdb)
custom_shapes: {}        # Define custom struct types for use in fields
include_ack_metadata: true  # Include ACKResourceMetadata in Status (default: true)
prefix_config:           # Override field path prefixes
  spec_field: ".Spec"
  status_field: ".Status"
```

---

## Resource-Level Config (`resources.<Name>`)

### Identity & Adoption

| Option | Type | Purpose |
|--------|------|---------|
| `is_arn_primary_key` | bool | Use ARN as primary identifier in ReadOne |
| `is_adoptable` | *bool | Whether resource can be adopted (default: true) |
| `shortNames` | []string | CRD aliases for `kubectl` (must be globally unique) |
| `ignore_idempotency_token` | bool | Auto-exclude fields with idempotencyToken trait |

### Reconciliation

| Option | Type | Purpose |
|--------|------|---------|
| `reconcile.requeue_on_success_seconds` | int | Re-sync interval after successful reconcile |

### Synced Condition

Tells the controller when a resource is considered synced (ready):

```yaml
synced:
  when:
    - path: Status.State     # Field path to check
      in: [ACTIVE, AVAILABLE]  # Acceptable values
```

All conditions in `when` must be satisfied.

### Updateable Guard

Prevents updates when the resource is in a transitional state:

```yaml
updateable:
  when:
    - path: Status.Status
      in: [ACTIVE]
  requeue_after_seconds: 30   # Default: 30
```

If the resource is NOT in an allowed state, the update is requeued.

### Deletable Guard

Prevents deletion when the resource is in a transitional state:

```yaml
deletable:
  when:
    - path: Status.Status
      in: [ACTIVE, FAILED]
  requeue_after_seconds: 30   # Default: 30
```

If the resource is NOT in an allowed state, the delete is requeued.

### Tags

```yaml
tags:
  ignore: true             # Skip tag handling entirely (resource doesn't support tags)
  path: "Spec.Tags"       # Override default tag field path
  key_name: "Key"          # Tag struct key member name
  value_name: "Value"      # Tag struct value member name
```

### Print / kubectl Columns

```yaml
print:
  add_age_column: true       # Show Age column in kubectl get
  add_synced_column: true    # Show Synced column (default: true)
  order_by: "index"          # Sort columns by "index" field
  additional_columns:
    - name: STATE
      json_path: ".status.state"
      type: string
      priority: 0            # 0 = standard view, >0 = wide view only
      index: 0               # Position (lower = leftmost)
```

### Compare

```yaml
compare:
  ignore:                    # Field paths to ignore in resource-level comparison
    - "Spec.Tags"
```

### Pre-Delete Sync

```yaml
pre_delete_sync:
  compare_all: true          # Include ALL spec fields in pre-delete delta (even ignored ones)
```

### Update Conditions Custom Method

```yaml
update_conditions_custom_method_name: "customUpdateConditions"
```

### Unpack Attributes Map

For APIs that use a `map[string]*string` Attributes pattern (SNS, SQS):

```yaml
unpack_attributes_map:
  set_attributes_single_attribute: true  # SetAttributes sets one attr at a time (SNS)
  get_attributes_input:
    overrides:
      FieldName:
        values: ["value1", "value2"]
```

---

## Operations Config

### Custom Operations (`resources.<Name>`)

| Option | Type | Purpose |
|--------|------|---------|
| `update_operation.custom_method_name` | string | Replace `sdkUpdate()` with custom method |
| `update_operation.omit_unchanged_fields` | bool | Only include changed fields in update request |
| `update_operation.only_set_unchanged_fields` | bool | Only set response fields for changed fields |
| `find_operation.custom_method_name` | string | Replace `sdkFind()` with custom method |
| `delete_operation.custom_method_name` | string | Replace `sdkDelete()` with custom method |

### List Operation

For List APIs that return all resources (no filtering):

```yaml
list_operation:
  match_fields:
    - Name              # Filter results by matching this field
    - ServiceId
```

### Top-Level Operations (`operations.<OperationName>`)

Override behavior for specific AWS API operations:

```yaml
operations:
  DescribeCluster:
    resource_name: Cluster           # Override inferred resource name
    operation_type: Get              # Override inferred type (Get, Create, Update, Delete, List)
    output_wrapper_field_path: Cluster.Details  # Unwrap nested output struct
    input_wrapper_field_path: Config.Settings   # Wrap input into nested struct
    override_values:
      FieldName: "value"             # Force a field to a constant value
    set_output_custom_method_name: customSetOutput  # Custom output processing
    custom_implementation: customOperation  # Entirely replace the operation
    custom_check_required_fields_missing_method: customCheck
```

**`operation_type`** — override when ACK heuristics fail. Accepts: `Get`, `Create`, `Update`, `Delete`, `List`. Can be a string or array.

**`resource_name`** — override when ACK incorrectly infers the resource from the operation name. Can be a string or array.

**`output_wrapper_field_path`** — when the API response nests the actual resource fields inside a struct (e.g., response has `Cluster.Details.Name` but you want `Name` in Status).

**`input_wrapper_field_path`** — when the API input nests resource fields inside a struct (e.g., input expects `Config.Settings.Name` but CRD has `Spec.Name`).

---

## Field-Level Config (`resources.<Name>.fields.<Field>`)

### Classification

| Option | Type | Purpose |
|--------|------|---------|
| `is_read_only` | bool | Force field into Status (override Spec inference) |
| `is_required` | *bool | Override required/optional from API model |
| `is_primary_key` | bool | Override default name/ID field detection |
| `is_owner_account_id` | bool | Route to `Status.ACKResourceMetadata.OwnerAccountID` |
| `is_arn` | bool | Override default ARN field detection |
| `is_attribute` | bool | Field is part of an Attributes map (SNS/SQS pattern) |
| `is_secret` | bool | Field becomes a SecretKeyReference |

### Immutability

| Option | Type | Purpose |
|--------|------|---------|
| `is_immutable` | bool | Enforce immutability via kubebuilder XValidation (prevents changes after set) |

### Type Override

```yaml
fields:
  Policies:
    type: "[]*string"        # Override inferred Go type
  CustomData:
    custom_field:
      list_of: ShapeName     # Create []ShapeName field
      map_of: ShapeName      # Create map[string]ShapeName field
```

### Go Tag Override

```yaml
fields:
  Type_:
    go_tag: 'json:"type,omitempty"'  # Fix underscore suffix from keyword collision
```

### Comparison

```yaml
fields:
  SecurityGroups:
    compare:
      is_ignored: true             # Exclude from delta (pair with delta_pre_compare hook)
      nil_equals_zero_value: true  # Treat nil and zero-value as equal
      pre_delete_include: true     # Include in pre-delete comparison even if ignored
```

### IAM Policy & Document Comparison

```yaml
fields:
  Policy:
    is_iam_policy: true    # Semantic IAM policy comparison (order-independent statements)
  Configuration:
    is_document: true      # Semantic JSON/YAML comparison (ignores whitespace/key order)
```

### Source Field (from another operation)

```yaml
fields:
  State:
    is_read_only: true
    from:
      operation: DescribeCluster   # Get value from this operation's output
      path: ClusterInfo.State      # Dot-path into the output shape
```

### Late Initialize

For server-defaulted fields (prevents nil-vs-value drift on first reconcile):

```yaml
fields:
  EngineVersion:
    late_initialize:
      min_backoff_seconds: 5
      max_backoff_seconds: 30
      skip_incomplete_check: {}   # Skip waiting for late-init to complete before marking synced
```

### References (Cross-Resource)

```yaml
fields:
  VpcId:
    references:
      resource: VPC                  # Referenced K8s resource type
      path: Status.VPCID            # Path to copy value from
      service_name: ec2              # Cross-service (omit for same-service!)
      skip_resource_state_validations: false  # Skip synced check (for cyclic refs)
```

**Important:** Do NOT set `service_name` for same-service references — it causes unresolved import errors.

### Set Field (Output→Resource type mismatch)

When the Go type differs between Input and Output shapes:

```yaml
fields:
  DBSecurityGroups:
    set:
      - method: Create           # Which operation (Create, Update, Delete, ReadOne)
        from: DBSecurityGroupName  # Extract this member from the output struct
      - method: ReadOne
        from: DBSecurityGroupName
      - method: Update
        to: NewFieldName         # Map resource field to different SDK input field
        ignore: true             # Skip setting resource field from this method's output
```

`ignore` can be: `true` (ignore resource setter), `"from"` (same), `"to"` (ignore SDK setter), `"all"` (both).

### Print Column

```yaml
fields:
  State:
    print:
      name: STATE             # Column header in kubectl get
      priority: 0             # 0 = standard, >0 = wide only
      index: 1                # Position order
```

---

## Renames (`resources.<Name>.renames`)

Fix stutter or inconsistent naming between operations. **Must specify rename for EACH operation that uses the field.**

```yaml
renames:
  operations:
    CreateBucket:
      input_fields:
        BucketName: Name
    DeleteBucket:
      input_fields:
        BucketName: Name
    DescribeBucket:
      input_fields:
        BucketName: Name
      output_fields:
        BucketIdentifier: ID
```

---

## Exception Handling (`resources.<Name>.exceptions`)

```yaml
exceptions:
  errors:
    404:
      code: ResourceNotFoundException     # Non-standard 404 error code
      message_prefix: "No resource"       # Optional: also check message prefix
      message_suffix: "does not exist"    # Optional: also check message suffix
  terminal_codes:
    - InvalidParameterException           # Errors that mark resource as unsyncable
    - ValidationException
```

---

## Hooks (`resources.<Name>.hooks`)

Hooks inject custom Go code at specific points. Use `code:` for one-liners or `template_path:` for complex logic.

```yaml
hooks:
  sdk_update_pre_build_request:
    code: "if err := rm.requeueIfNotRunning(latest); err != nil { return nil, err }"
  sdk_create_post_set_output:
    template_path: templates/hooks/cluster/sdk_create_post_set_output.go.tpl
```

### Available Hook Points

**SDK operation hooks** (prefix with `sdk_create_`, `sdk_read_one_`, `sdk_update_`, `sdk_delete_`):
- `*_pre_build_request` — before building SDK input shape (can short-circuit with early return)
- `*_post_build_request` — after input built, before API call (modify input, remove fields)
- `*_post_request` — immediately after API call returns (custom error handling)
- `*_pre_set_output` — before processing API response into `ko` object
- `*_post_set_output` — after merging API response (final state modifications)

**Other SDK hooks:**
- `sdk_file_end` — appended at end of sdk.go (helper functions)

**Comparison hooks:**
- `delta_pre_compare` — before auto-generated field comparison (custom normalization)
- `delta_post_compare` — after all fields compared (add custom deltas)

**Lifecycle hooks:**
- `late_initialize_pre_read_one` / `late_initialize_post_read_one` — around late-init ReadOne
- `references_pre_resolve` / `references_post_resolve` — around reference resolution
- `ensure_tags` / `convert_tags` — custom tag sync and format conversion

---

## Common Gotchas

- **All aws-sdk-go fields are pointers** — always nil-check before dereferencing
- **Tag field not found** — add `tags.ignore: true` if resource doesn't support tags
- **Late-init delta mismatches** — use `late_initialize: {}` with `skip_incomplete_check: {}` for server-defaulted fields
- **Unordered list comparison** — use `compare.is_ignored` + `delta_pre_compare` hook
- **Different field names across operations** — use `from:` to map from non-Create operations
- **Renames must cover all operations** — missing a rename on one operation causes mismatched field names
- **Same-service references** — do NOT set `service_name`, it causes unresolved import alias errors
- **`output_wrapper_field_path`** — use when API wraps response in a nested struct; flattens it
- **`input_wrapper_field_path`** — use when API expects input fields nested inside a wrapper struct
