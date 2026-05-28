# Plan Output Schema

The Planner must produce a document with exactly these sections. Every section is required. Use "N/A" for genuinely inapplicable items — never leave blanks.

---

## Resource Summary

- **Service:** `<aws-service-name>` (e.g., `backup`, `ecr`, `s3`)
- **Resource:** `<ResourceName>` (e.g., `BackupVault`, `Repository`)
- **Primary Key Field:** `<OriginalFieldName>` → `<RenamedField>` (if renamed)
- **AWS-Assigned Identifiers:** List of fields assigned by AWS after creation (e.g., ARN, ID, CreationDate)

## CRUD Operations

| Operation | AWS API Name | Exists? | Notes |
|-----------|-------------|---------|-------|
| Create    |             | Yes/No  |       |
| Read      |             | Yes/No  | Describe vs Get vs List-single |
| Update    |             | Yes/No  | Update vs Put vs None |
| Delete    |             | Yes/No  |       |
| List      |             | Yes/No  |       |

## Field Inventory

| Field Name (Original) | Rename To | In Create Input | In Read Output | In Update Input | Spec/Status | Mutable | Notes |
|----------------------|-----------|----------------|----------------|-----------------|-------------|---------|-------|

Include all fields from the Create input shape and Read output shape. Mark fields that appear only in the output as Status.

## Renames

| Original Field | Renamed To | Operations Requiring Rename | Input/Output |
|---------------|-----------|---------------------------|--------------|

List every operation where the renamed field appears. This is critical — missing a rename in any operation causes build failures.

## Immutable Fields

| Field | Reason |
|-------|--------|

Fields that cannot be changed after creation (e.g., primary key, encryption type).

## Error Handling

| Scenario | HTTP Code | AWS Error Code | Notes |
|----------|-----------|---------------|-------|
| Not Found (404) |   |               | Some APIs return AccessDeniedException instead of ResourceNotFoundException |
| Already Exists |    |               |       |
| Terminal State |    |               | Errors that mean the resource cannot be reconciled |

## Tags

- **Supports Tags:** Yes/No
- **Tagging API:** TagResource/UntagResource | Inline (tags in Create input) | Both
- **Configuration:** `tags.ignore: true` if using TagResource API (ACK handles it automatically)
- **Rationale:** Why this configuration

## Wrapper Fields

| Operation | input_wrapper_field_path | output_wrapper_field_path | Notes |
|-----------|------------------------|--------------------------|-------|

When the API wraps request/response fields in a nested structure (e.g., `CreateBackupPlan` wraps fields in a `BackupPlan` object), document the path here.

## Fields Outside Wrapper

| Field | Location | How to Handle |
|-------|----------|---------------|

Fields that exist at the top level of the request but are not inside the wrapper (if wrapper is used). These typically require custom hooks.

## Cross-Resource References

| Field | Referenced Resource | Referenced Service | Field Path | Same-Service? |
|-------|-------------------|--------------------|------------|--------------|

Same-service references omit `service_name` in generator.yaml. Cross-service references must include it.

## Custom Hooks Required

| Hook Point | Purpose | Key Logic |
|-----------|---------|-----------|
| e.g., sdk_create_post_set_output | Set fields not in wrapper | Copy ARN from response |

Only list hooks that are actually needed. Do not propose hooks for behavior that generator.yaml can handle.

## Implementation Notes

Capture any non-standard patterns, gotchas, or special considerations that don't fit in the sections above. Examples:
- Resource uses Put instead of Update (full replacement semantics)
- Eventual consistency concerns
- Resource has async creation (need custom status conditions)
- Fields with special serialization requirements
