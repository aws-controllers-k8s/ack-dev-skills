---
name: ack-dev
description: >-
  Guide for AWS Controllers for Kubernetes (ACK) development. Use when working
  in an ACK service controller repository or the code-generator. Covers setting up
  dev environments, creating new controllers, adding resources or fields to CRDs,
  configuring code generation, writing custom hooks, implementing cross-resource
  references, writing E2E tests, and submitting PRs.
license: Apache-2.0
metadata:
  author: ACK Team
  version: "1.0.0"
---

# ACK Development Guide

## Overview

AWS Controllers for Kubernetes (ACK) lets you manage AWS resources directly from Kubernetes. It consists of three components:

1. **Runtime** - Shared library: base controller logic, AWS SDK integration, reconciliation framework
2. **Code Generator** - Generates CRDs, Go types, controller logic, and SDK bindings from AWS API models
3. **Service Controllers** - Individual controllers per AWS service, built from generated code + custom hooks

```
AWS API Model → Code Generator → Generated Code → Controller
     ↓              ↓              ↓
  service.json  generator.yaml  CRDs + Go types
```

## Working Conventions

1. **Use available resources** - Ask if local clones of upstream repos are available before trying to fetch remote content.
2. **Feed the skill** - When you discover gaps, new patterns, or fixes not covered here, propose updating the relevant file in this skill (SKILL.md or references/). Capture what you learned so the next session benefits.

---

## Golden Rules

These apply everywhere. They are not repeated in individual sections.

**Never use aws-sdk-go v1.** The Go module `github.com/aws/aws-sdk-go` (no `-v2` suffix) is deprecated. ACK uses `github.com/aws/aws-sdk-go-v2`. When looking for API models, SDK types, or operation definitions, always use the v2 module paths. The `AWS_SDK_GO_VERSION` env var below refers to the Go module version of the v2 SDK (e.g., `v1.41.0` is the module version, not the SDK generation).

**Never manually edit generated files.** All files in `apis/v1alpha1/`, `pkg/resource/`, `config/crd/`, `config/rbac/`, `helm/`, and `cmd/controller/main.go` are generated and will be overwritten. If something's wrong, fix `generator.yaml` and rebuild.

**Edit only these:**
- `generator.yaml` - All resource configuration
- `templates/hooks/` - Custom hook templates (if needed)
- `test/e2e/` - E2E tests

**Always use `make build-controller`** from the code-generator directory. It handles everything in one shot: API types, controller code, deepcopy, CRDs, RBAC, Helm chart, gofmt, and go mod tidy. Individual `ack-generate` commands can leave partial state.

```bash
# From code-generator directory
SERVICE=<service> AWS_SDK_GO_VERSION=v1.41.0 make build-controller
```

Set `AWS_SDK_GO_VERSION` explicitly for reproducibility. Use the core SDK version (`github.com/aws/aws-sdk-go-v2`), not the service-specific version.

**Only configure non-default fields in generator.yaml.** If a field uses all defaults (mutable, no references, etc.), don't add it. Less config = less maintenance.

**Squash commits before final push:**
```bash
git reset --soft <base-commit>
git commit -m "add support for <Resource> resource"
git push --force origin <branch>
```

---

## Adding a New Field to a CRD

**Before starting:** Identify the AWS API field, check if it's already in the CRD, review similar fields for patterns.

**Steps:**
1. Update `generator.yaml` (only if field needs non-default behavior)
2. Rebuild: `SERVICE=<svc> AWS_SDK_GO_VERSION=<ver> make build-controller`
3. Check generated code: `git diff apis/v1alpha1/` and `git diff config/crd/`
4. Add custom logic if needed in `pkg/resource/<resource>/hooks.go`
5. Add tests and test locally: `make test`

**Renaming Fields for Better UX:**

AWS API field names often include redundant prefixes (e.g., `BackupVaultName`). ACK allows renaming to more idiomatic Kubernetes names.

```yaml
resources:
  BackupVault:
    fields:
      Name:
        is_primary_key: true
    renames:
      operations:
        CreateBackupVault:
          input_fields:
            BackupVaultName: Name
            BackupVaultTags: Tags
        DeleteBackupVault:
          input_fields:
            BackupVaultName: Name
        DescribeBackupVault:
          input_fields:
            BackupVaultName: Name
```

**Important:** Add renames for ALL operations that use the field (Create, Read, Update, Delete, List).

**Renaming primary key fields:** Requires both the renamed field key in `fields:` AND renames on every operation. For AWS-assigned identifiers (output-only fields like `BackupPlanId`), include `output_fields` renames on Create and Get, plus `input_fields` renames on Get, Update, and Delete. Missing any operation causes cryptic code-gen errors like `could not find field with path`.

**Common field patterns:**
- **Immutable fields**: Check AWS API docs carefully - a field being "required" in Update doesn't mean it's mutable. Primary keys and lookup identifiers are almost always immutable.
- **References to other resources**: Use `AWSResourceReferenceWrapper` type via `references` config in generator.yaml.
- **Sensitive data**: Store in Secrets, reference from spec.

**Field Immutability - How to Verify:**

A field should be marked `is_immutable: true` if:
1. AWS API docs say "cannot be changed" or "immutable"
2. The field is a primary key or lookup identifier (even if required in Update)
3. Testing with AWS CLI shows the field cannot be updated

**Nested Response Handling (`output_wrapper_field_path`):**

Some AWS APIs wrap responses in a nested object. Use `output_wrapper_field_path` to flatten them. See [code-generation.md](references/code-generation.md) for full details and examples.

**Nested Input Handling (`input_wrapper_field_path`):**

Some AWS APIs wrap input fields in a nested structure. Use `input_wrapper_field_path` to flatten the wrapper's fields into the CRD Spec. See [code-generation.md](references/code-generation.md) for internals, limitations, and handling fields outside the wrapper.

---

## Configuring Tags Support

**Important:** Not all resources support tagging. Check AWS documentation first.

```bash
aws <service> tag-resource help
# Look for: "Currently, the only supported resource is..."
```

### Resources that do NOT support tagging

```yaml
resources:
  RepositoryCreationTemplate:
    tags:
      ignore: true
```

### Resources that DO support tagging

When a resource supports tagging via TagResource/UntagResource (or service-specific equivalents like CreateTags/DeleteTags, TagRole/UntagRole), ACK requires both generated and manual code to fully wire up tag management.

**generator.yaml** — do NOT set `tags.ignore: true`. Either omit the `tags:` section (defaults to `ignore: false`) or set it explicitly:

```yaml
resources:
  MyResource:
    # tags.ignore defaults to false — tags ARE supported
```

**What the code-generator produces automatically** when `tags.ignore` is `false`:
- `pkg/resource/<resource>/tags.go` — `convertToOrderedACKTags`, `fromACKTags`, `ignoreSystemTags`, `syncAWSTags` helper functions
- `pkg/resource/<resource>/manager.go` — `GetDefaultTags`, `MergeResourceTags` integration
- `pkg/resource/<resource>/delta.go` — tag comparison logic that calls `convertToOrderedACKTags`
- A `Tags` field in the resource's `Spec`

**What you must implement manually:**

1. **A shared tag sync utility** (one per controller, reused by all tagged resources). Location varies by controller convention — check what already exists:
   - `pkg/sync/tags.go` (e.g., kafka-controller)
   - `pkg/util/tags.go` (e.g., elasticache-controller, rds-controller, iam-controller)
   - `pkg/tags/sync.go` (e.g., ec2-controller)

   If the controller already has one, reuse it. If not, create one. The function computes the diff between desired and latest tags, then calls the appropriate AWS APIs to add/remove tags.

2. **A per-resource `syncTags` function** that bridges the resource to the shared utility. This goes in `hooks.go` or is declared as a variable pointing to the shared function:

   **Pattern A — method delegating to shared util** (elasticache, kafka):
   ```go
   func (rm *resourceManager) syncTags(ctx context.Context, desired *resource, latest *resource) error {
       return util.SyncTags(ctx, desired.ko.Spec.Tags, latest.ko.Spec.Tags,
           latest.ko.Status.ACKResourceMetadata, convertToOrderedACKTags,
           rm.sdkapi, rm.metrics)
   }
   ```

   **Pattern B — variable alias to shared package** (ec2):
   ```go
   var syncTags = tags.Sync
   ```

   **Pattern C — inline implementation** (iam, for service-specific APIs like TagRole/UntagRole):
   ```go
   func (rm *resourceManager) syncTags(ctx context.Context, desired *resource, latest *resource) error {
       // Compute diff, call service-specific tag/untag APIs directly
   }
   ```

3. **A hook template** that checks for tag changes during update. This is typically in `templates/hooks/<resource>/sdk_update_pre_build_request.go.tpl`:

   ```go
   if delta.DifferentAt("Spec.Tags") {
       if err = rm.syncTags(ctx, desired, latest); err != nil {
           return nil, err
       }
   }
   if !delta.DifferentExcept("Spec.Tags") {
       return desired, nil
   }
   ```

   The second check (`DifferentExcept`) short-circuits the rest of the update logic if ONLY tags changed — tag updates use their own API and don't go through the standard Update operation.

4. **Wire the hook template in generator.yaml:**

   ```yaml
   resources:
     MyResource:
       hooks:
         sdk_update_pre_build_request:
           template_path: hooks/<resource>/sdk_update_pre_build_request.go.tpl
   ```

   The `sdk_update_pre_build_request` hook is sufficient for tag syncing — a `custom_method_name: customUpdate` is NOT required just for tags. Only use `customUpdate` if the resource needs it for other reasons. In that case, add the tag delta check directly into the `customUpdate` function in `hooks.go` instead of using a hook template.

### How to determine the implementation approach

1. **Check if the controller already has a shared tag utility** — look for `pkg/sync/`, `pkg/util/tags.go`, or `pkg/tags/`. If it exists, follow the same pattern for your new resource.
2. **Check existing resources in the controller** — look at how other resources in the same controller handle tags (their hooks.go and hook templates). Follow the established convention.
3. **Identify the service's tag API names** — services use different APIs:
   - Most: `TagResource` / `UntagResource` / `ListTagsForResource`
   - EC2: `CreateTags` / `DeleteTags` / `DescribeTags`
   - IAM: `TagRole` / `UntagRole` / `ListRoleTags` (per-resource-type APIs)
   - S3: `PutBucketTagging` / `DeleteBucketTagging` / `GetBucketTagging`

### Tag reading (ListTagsForResource)

How tags are read on reconcile depends on the service:
- **Tags in Describe response** (EC2, RDS, Kafka): Tags come back automatically from the Describe/Get API. No additional hook needed.
- **Separate ListTagsForResource API** (ElastiCache, IAM, Lambda): Requires a `sdk_read_one_post_set_output` hook or supplemental API call in the read path to fetch tags.

Check the existing controller's read hooks — if other resources fetch tags via ListTagsForResource, your new resource likely needs the same pattern.

### Special cases

- Some resources have a field for tags applied to OTHER resources they create (e.g., ECR RepositoryCreationTemplate's `resourceTags`). Set `tags.ignore: true` for these.
- Some services use a `TagSet` or `TagList` structure instead of a flat map. Use `tags.path` in generator.yaml to specify the nested path (e.g., S3: `tags: path: Tagging.TagSet`).

---

## Implementing Cross-Resource References

**When to use:** One ACK resource needs to reference another (e.g., EC2 instance referencing a VPC).

```yaml
resources:
  RepositoryCreationTemplate:
    fields:
      CustomRoleARN:
        references:
          resource: Role
          service_name: iam
          path: Status.ACKResourceMetadata.ARN
```

The code-generator handles reference resolution automatically. The generated code creates a `CustomRoleRef` field alongside `CustomRoleARN` and resolves the reference at reconciliation time.

**ACK convention:** Return error on invalid reference, don't create resource.

**Same-service references: do NOT set `service_name`.** When referencing a resource in the same controller (e.g., BackupPlan referencing BackupVault), omit `service_name`. Setting it (even correctly, e.g., `service_name: backup`) causes the generated code to produce an unresolved import alias (`backupapitypes`) and a compile error. Without `service_name`, code-gen correctly uses the local API types. Only set `service_name` for cross-service references (e.g., IAM Role, KMS Key).

---

## Error Codes and Custom Hooks

**Prefer `exceptions.errors` over custom hooks for error code mapping.**

Many AWS APIs return non-standard error codes for 404 (not found). Use `exceptions.errors.404.code` in generator.yaml:

```yaml
resources:
  BackupVault:
    exceptions:
      errors:
        404:
          code: AccessDeniedException  # DescribeBackupVault returns 403 for non-existent vaults
  BackupPlan:
    exceptions:
      errors:
        404:
          code: ResourceNotFoundException
```

**Custom hooks** are for cases where declarative config isn't enough (e.g., complex conditional logic, extra API calls).

1. Create hook template: `templates/hooks/<resource>/sdk_<hook_point>.go.tpl`
2. Reference in generator.yaml:
   ```yaml
   resources:
     BackupPlan:
       hooks:
         sdk_update_post_build_request:
           template_path: hooks/backup_plan/sdk_update_post_build_request.go.tpl
   ```
3. Rebuild (custom templates are picked up automatically by `make build-controller`)

**Hook template must use renamed fields:** If you renamed fields in generator.yaml, use the new names (e.g., `r.ko.Spec.Name` not `r.ko.Spec.BackupVaultName`).

**Common hook points:**
- `sdk_read_one_post_request` - After reading resource from AWS
- `sdk_create_pre_build_request` / `sdk_create_post_build_request` - Before/after building create input
- `sdk_update_pre_build_request` / `sdk_update_post_build_request` - Before/after building update input
- `sdk_delete_pre_build_request` - Before building delete input

---

## Code Generation Quick Reference

For customization patterns (skip fields, rename fields, mark immutable, custom hooks), see [code-generation.md](references/code-generation.md).

---

## PR Checklist for New Resources

### Required Files

| File/Location | Purpose |
|---------------|---------|
| `generator.yaml` | Resource config (remove from ignore, add fields/renames/hooks) |
| `apis/v1alpha1/` | Generated API types |
| `pkg/resource/<resource>/` | Generated controller code |
| `config/crd/bases/` | Generated CRD definitions |
| `helm/crds/` | CRD for Helm chart (auto-generated) |
| `helm/values.yaml` | `reconcile.resources` list (auto-generated) |
| `test/e2e/tests/test_<resource>.py` | E2E tests (create, update, delete) |
| `test/e2e/resources/<resource>.yaml` | Test resource template |

### Pre-Submit Checklist

```
[ ] Resource removed from `ignore.resource_names` in generator.yaml
[ ] All CRUD operations configured
[ ] Code generated: SERVICE=<svc> AWS_SDK_GO_VERSION=<ver> make build-controller
[ ] git status shows all expected generated files including Helm
[ ] Code compiles: go build -o bin/controller ./cmd/controller
[ ] E2E tests added with create/update/delete coverage
[ ] E2E tests verify Synced condition after operations
[ ] Commits squashed into single commit
```

### Workflow Summary

1. **Edit only:** `generator.yaml`, `test/e2e/`
2. **Build:** `cd code-generator && SERVICE=<svc> AWS_SDK_GO_VERSION=<ver> make build-controller`
3. **Verify:** `git status` shows all expected generated files including Helm
4. **Test:** `source .venv/bin/activate && pytest test/e2e/tests/test_<resource>.py -v`
5. **Commit:** Single squashed commit
6. **Push:** Force push to PR branch

For PR ordering when building new controllers, see [pr-workflow.md](references/pr-workflow.md).

---

## Reference Files

- [Environment Setup](references/environment-setup.md) — Read when setting up a dev environment or cloning repos
- [Code Generation Deep Dive](references/code-generation.md) — Read when debugging code-gen output, wrapper fields, or OriginalShapeName issues
- [Testing](references/testing.md) — Read when writing or debugging E2E tests
- [Running E2E Tests](references/running-e2e-tests.md) — Read when running e2e tests locally with KIND via test-infra
- [Contributing to Code-Generator](references/contributing-codegen.md) — Read when making changes to the code-generator itself
- [PR Workflow](references/pr-workflow.md) — Read when planning PR order for new controllers or cutting releases
- [Troubleshooting](references/troubleshooting.md) — Read when debugging build failures, controller issues, or test problems

Quick search across references:
```bash
grep -ri "wrapper" references/
grep -ri "immutable" references/
grep -ri "hook" references/
```

## Scripts

Run these from the service controller directory:

- **`scripts/build-controller.sh <service> [sdk-version] [codegen-path]`** - Builds a controller with correct env vars. Auto-detects code-generator location. Builds `ack-generate` if needed.
- **`scripts/verify-build.sh`** - Post-build check: compiles the controller, reports changed files by area, warns if Helm chart wasn't updated.
- **`scripts/setup-e2e.sh`** - Creates Python venv, installs test dependencies and setuptools. Handles the Python 3.13+ gotcha.
