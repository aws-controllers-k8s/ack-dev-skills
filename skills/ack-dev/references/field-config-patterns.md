# Field Configuration Patterns

Distilled from 6,300+ PR review comments across 55 ACK repos. These are the patterns reviewers consistently enforce.

## Contents
- Pre-Generation: Read the SDK Source
- Field Placement (Spec vs Status)
- is_read_only + from Pattern
- is_immutable Decision Tree
- is_primary_key
- is_secret (Sensitive Fields)
- Custom Fields (type override)
- Ignoring Noise Fields
- ignore_idempotency_token
- Fixing Reserved Keyword Field Names
- server_side_defaults and Late Initialization
- Terminal Codes
- Declarative Synced Condition

## Pre-Generation: Read the SDK Source

Before configuring `generator.yaml`, read the `aws-sdk-go-v2` service code to understand the API shapes. This prevents most configuration mistakes.

**What to look for:**
1. **Deprecated fields** — marked with `// Deprecated:` comments in SDK types. Ignore them.
2. **Required fields** on Describe/Get input — these are your primary key candidates
3. **Output-only fields** — fields only in Describe output, not in Create input → Status candidates
4. **Sensitive fields** — passwords, private keys, passphrases → `is_secret` candidates
5. **RequestId / HTTP status fields** — always noise, ignore them
6. **Exception types** — map user-caused errors to terminal codes

```go
// Example: spot deprecated fields in SDK source
// Deprecated: Only used in the legacy data preparation experience.
LogicalTableMap map[string]types.LogicalTable
```

Ignore deprecated fields in generator.yaml:
```yaml
ignore:
  field_paths:
    # LogicalTableMap - deprecated, only used in legacy data preparation
    - CreateDataSetInput.LogicalTableMap
    - UpdateDataSetInput.LogicalTableMap
    - DescribeDataSetOutput.LogicalTableMap
```

## Field Placement (Spec vs Status)

The code-generator infers field placement from AWS API shapes:
- Fields in **Create input** → `Spec`
- Fields **only** in Describe/Get output → `Status`

**Common mistake:** A field appears in Describe output but is also user-settable (e.g., it's in the Update API). Code-gen puts it in Status, but it should be in Spec.

**Fix:** Use `from` to override placement:
```yaml
fields:
  EncryptionType:
    from:
      operation: DescribeRepository
      path: EncryptionConfiguration.EncryptionType
```

This tells code-gen: "this field's value comes from the Describe output, but put it in Spec."

**Rule of thumb:**
- If users set it → Spec
- If only AWS sets it → Status (use `is_read_only: true`)
- If users set it AND it comes from a different API shape → Spec with `from`

## is_read_only + from Pattern

For output-only fields that should appear in Status:

```yaml
fields:
  CreatorRequestID:
    is_read_only: true
    from:
      operation: GetBackupPlan
      path: CreatorRequestId
  DeletionDate:
    is_read_only: true
    from:
      operation: GetBackupPlan
      path: DeletionDate
  LastExecutionDate:
    is_read_only: true
    from:
      operation: GetBackupPlan
      path: LastExecutionDate
```

**Key points:**
- `is_read_only: true` puts the field in Status
- `from.operation` specifies which API call provides the value
- `from.path` is the dot-path in the API response
- The field name in `fields:` is the CRD field name (can differ from API path)

**Gotcha:** `is_immutable` does NOT apply to Status fields. Reviewers flag this: "ID is in the Status fields so I don't think is_immutable applies."

## is_immutable Decision Tree

Mark a field `is_immutable: true` when:
1. AWS API docs say "cannot be changed" or "immutable"
2. The field is a primary key or lookup identifier
3. The field is NOT in the Update API's input shape

```yaml
fields:
  AddressFamily:
    is_immutable: true
```

**Nuance from reviewers:**

Don't blindly mark fields immutable just because there's no Update API. Consider:
- If the Create API validates the field (e.g., checks IAM role exists), allowing modification lets users fix typos without recreating the resource
- If the field is truly server-side immutable (e.g., VPC CIDR), mark it

**Example (backup-controller PR#7):** "We might want to consider removing this immutable check. While there isn't an update API operation, it is possible that the CreateBackupSelection operation performs some validation on the IAM role and fail to create a new AWS resource. In that case we would want to allow users to modify this field without making them re-create the ACK resource."

## is_primary_key

Marks the field used to identify the resource in AWS API calls:

```yaml
fields:
  Name:
    is_primary_key: true
```

**Common patterns:**
- AWS-assigned IDs (e.g., `BackupPlanId`): Usually in Status, set via `is_read_only: true`
- User-provided names (e.g., `BackupVaultName`): In Spec, often renamed to `Name`
- ARN-based: Usually handled automatically via `Status.ACKResourceMetadata.ARN`

**Gotcha:** `is_primary_key` fields are NOT automatically included in the generated `checkRequiredFieldsMissingFromShape` check for ReadMany operations. If your resource uses a List API (not Get), you may need custom handling.

## is_secret (Sensitive Fields)

Fields containing credentials, passwords, or private keys must be stored in Kubernetes Secrets:

```yaml
fields:
  Credentials.CredentialPair.Password:
    is_secret: true
  Credentials.KeyPairCredentials.PrivateKey:
    is_secret: true
  Credentials.KeyPairCredentials.PrivateKeyPassphrase:
    is_secret: true
```

**How to identify:** Search the SDK types for fields named `Password`, `Secret`, `PrivateKey`, `Passphrase`, `Token` (auth tokens, not idempotency tokens), `Credential`.

## Custom Fields (type override)

When a field doesn't exist in any API shape but you need it in the CRD:

```yaml
fields:
  BackupPlanID:
    is_immutable: true
    is_required: true
    type: string
    references:
      resource: BackupPlan
      path: Status.BackupPlanID
```

**When to use:**
- Fields outside an `input_wrapper_field_path` that are needed for CRUD
- Synthetic fields that combine multiple API fields
- Fields needed for cross-resource references

**Important:** Custom fields with `type:` override need hooks to wire them into SDK requests. Code-gen won't auto-map them.

## ignore_idempotency_token

Many AWS APIs have idempotency token fields (e.g., `ClientToken`, `CreatorRequestId`). These clutter the CRD with no user value.

```yaml
ignore_idempotency_token: true
```

**This is opt-out** (enabled by default for new controllers). Existing controllers that already expose these fields in their CRD should NOT enable this to avoid breaking changes. The `crd-compatibility-check` Prow job catches this.

## Ignoring Noise Fields

AWS API responses often include fields that are never useful in a CRD. Always ignore:

**RequestId / HTTP status code fields:**
```yaml
ignore:
  field_paths:
    - CreateDataSourceOutput.RequestId
    - UpdateDataSourceOutput.RequestId
    - CreateDataSourceOutput.Status    # HTTP status, not resource status
    - UpdateDataSourceOutput.Status
```

**Deprecated fields** (check SDK source for `// Deprecated:` comments):
```yaml
ignore:
  field_paths:
    # Deprecated: Only used in legacy data preparation experience
    - CreateDataSetInput.LogicalTableMap
    - UpdateDataSetInput.LogicalTableMap
    - DescribeDataSetOutput.LogicalTableMap
```

**Rule:** Ignore on both input AND output shapes. Missing either side causes the field to still appear in the CRD.

**New API fields appearing unexpectedly:** When AWS adds new fields to an API, they appear in generated code after rebuilding with a newer SDK. If the field isn't relevant to the CRD, ignore it on all shapes:
```yaml
ignore:
  field_paths:
    - CreateFunctionInput.NewUnsupportedField
    - CreateFunctionOutput.NewUnsupportedField
    - GetFunctionOutput.NewUnsupportedField
```

## Fixing Reserved Keyword Field Names

Go reserved keywords used as field names get a trailing underscore in generated code (e.g., `Type` → `Type_`). This produces ugly CRD field names.

**Fix with `go_tag` override:**
```yaml
resources:
  AutoScalingGroup:
    fields:
      TrafficSources.Type:
        go_tag: json:"type,omitempty"
```

**How to spot:** Examine the generated CRD at `helm/crds/*.yaml` and look for field names ending in underscore.

## server_side_defaults and Late Initialization

Late initialization populates Spec fields with server-assigned defaults after creation.

**Critical rule:** Late initialization only works for Spec fields, NOT Status fields.

```yaml
fields:
  EncryptionType:
    late_initialize: {}
```

**Common mistake (ec2-controller PR#235):** Trying to use late initialization for Status fields. "Late initialization code generator looks for these fields in Spec, however I am trying to update the fields within Status."

**When late init is NOT enough (rds-controller PR#276):** "If the DBCluster changes the value of these fields after the DBInstance has late initialized them, the controller will still see a delta and attempt to update them directly on the DBInstance." In this case, use hooks to ignore fields conditionally.

## Terminal Codes

Terminal codes indicate **unrecoverable** errors where the resource spec must be changed:

```yaml
resources:
  BackupVault:
    exceptions:
      terminal_codes:
        - InvalidParameterValueException
        - MissingParameterValueException
        - AlreadyExistsException
```

**Critical distinction (rds-controller PR#105, jaypipes):**
- **Terminal:** Bad spec that can never succeed (e.g., invalid parameter, malformed policy)
- **NOT terminal:** Quota exceeded, rate limited, transient AWS errors

"Terminal conditions represent that the resource's desired state needs to be changed. Quota exceeded is recoverable — the user can requeue at a later time when another resource has been deleted."

**Rule:** If the same spec could succeed on retry (quota freed, rate limit passed), it's NOT terminal.

## Declarative Synced Condition

For async resources with a status/state field, use the declarative `synced.when` config instead of writing hook code:

```yaml
resources:
  DataSource:
    synced:
      when:
        - path: Status.Status
          in:
            - CREATION_SUCCESSFUL
            - UPDATE_SUCCESSFUL
```

This auto-generates the `IsSynced()` logic. The resource is marked `ACK.ResourceSynced = True` only when the status field matches one of the listed values. All other states (CREATING, UPDATING, DELETING, etc.) result in `Synced = False` and a requeue.

**When to use:** Any resource with a status/state enum that transitions through intermediate states.

**When NOT to use:** Resources with complex sync logic (e.g., need to check multiple fields, make additional API calls). Use `IsSynced()` hook instead.
