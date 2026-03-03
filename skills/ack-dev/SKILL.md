---
name: ack-dev
description: >-
  Guide for AWS Controllers for Kubernetes (ACK) development. Use when setting up
  ACK dev environments, creating new controllers, adding resources or fields to CRDs,
  configuring code generation, writing custom hooks, implementing cross-resource
  references, writing E2E tests, or submitting PRs for ACK service controllers.
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

## Communication Style

**Be direct and action-oriented:**
- "Added `DatabaseName` field to spec. Run `make build-controller`"
- "The field needs `is_immutable: true` in generator.yaml"
- Don't ask "Would you like me to..." - just do it or explain what to do
- Don't explain basic concepts unless asked

**Working principles:**
1. **Do it right, not fast** - Prefer correct solutions over quick-and-dirty shortcuts.
2. **Ask before committing** - Never commit/push without confirmation.
3. **Use available resources** - Ask if local clones of upstream repos are available before trying to fetch remote content.
4. **Feed the skill** - When you discover gaps, new patterns, or fixes not covered here, propose updating the relevant file in this skill (SKILL.md or references/). Capture what you learned so the next session benefits.

---

## Golden Rules

These apply everywhere. They are not repeated in individual sections.

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

**Nested Input Handling (`input_wrapper_field_path`):**

Some AWS APIs wrap *input* fields in a nested structure. With `input_wrapper_field_path`, the wrapper's fields are flattened directly into the CRD Spec.

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
- During CRD construction (`model.go`), the wrapper's member fields are added to Spec instead of the wrapper itself
- During code generation (`set_sdk.go`), a wrapper struct variable (`fw`) is created, populated from Spec fields, then assigned to the input shape's wrapper field
- The `getWrapperShape` function in `crd.go` handles both input and output unwrapping, including list-of-structure wrappers

---

## Configuring Tags Support

**Important:** Not all resources support tagging via the TagResource API. Check AWS documentation first.

```bash
aws <service> tag-resource help
# Look for: "Currently, the only supported resource is..."
```

**For resources that support TagResource:**
```yaml
resources:
  Repository:
    tags:
      ignore: false  # Default
```

**For resources that do NOT support TagResource:**
```yaml
resources:
  RepositoryCreationTemplate:
    tags:
      ignore: true
```

**Special case:** Some resources have a field for tags applied to OTHER resources they create (e.g., ECR RepositoryCreationTemplate's `resourceTags`). The template still needs `tags.ignore: true`.

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

**Team decision** (from tech lead a-hilaly): Return error on invalid reference, don't create resource.

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

**How customization works:**
- **Skip fields**: Add to `ignore.field_paths` in generator.yaml
- **Rename fields**: Use `renames.operations` in generator.yaml
- **Mark immutable**: Set `is_immutable: true`
- **Add validation**: Use kubebuilder markers in custom types
- **Custom conversion**: Implement in hooks

For deep code-generation internals, see [code-generation.md](references/code-generation.md).

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

- [Environment Setup](references/environment-setup.md) - Dev environment prerequisites, cloning repos, building code-generator
- [Code Generation Deep Dive](references/code-generation.md) - Internals, OriginalShapeName, wrapper handling details
- [Testing](references/testing.md) - E2E test setup, file structure, full test patterns, common issues
- [Contributing to Code-Generator](references/contributing-codegen.md) - Test patterns, fixtures, PR workflow for code-gen changes
- [PR Workflow](references/pr-workflow.md) - PR ordering for new controllers, bootstrap PRs, resource PRs
- [Troubleshooting](references/troubleshooting.md) - Common issues, debugging tips, resources and links

## Scripts

Run these from the service controller directory:

- **`scripts/build-controller.sh <service> [sdk-version] [codegen-path]`** - Builds a controller with correct env vars. Auto-detects code-generator location. Builds `ack-generate` if needed.
- **`scripts/verify-build.sh`** - Post-build check: compiles the controller, reports changed files by area, warns if Helm chart wasn't updated.
- **`scripts/setup-e2e.sh`** - Creates Python venv, installs test dependencies and setuptools. Handles the Python 3.13+ gotcha.
