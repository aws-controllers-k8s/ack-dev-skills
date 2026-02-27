---
inclusion: manual
---

# ACK Development Guide

## Overview

This guide helps you work with AWS Controllers for Kubernetes (ACK) - from setting up your development environment to implementing new features and debugging controllers. It provides step-by-step workflows based on team practices and architectural decisions.

## Communication Style

**Be direct and action-oriented:**

- ✅ "Added `DatabaseName` field to spec. Run `make build-controller`"
- ✅ "The field needs `is_immutable: true` in generator.yaml"
- ❌ Don't ask "Would you like me to..." - just do it or explain what to do
- ❌ Don't explain basic concepts unless asked

**Working principles:**

1. **Do it right, not fast** - Prefer correct solutions over quick-and-dirty shortcuts.
2. **Ask before committing** - Never commit/push without confirmation.
3. **Use available resources** - Ask if local clones of upstream repos are available before trying to fetch remote content.

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

## Common Workflows

### 1. Setting Up ACK Development Environment

**Prerequisites:**
- Go 1.23+ (`go version`)
- Docker (`docker --version`)
- kubectl configured (`kubectl version`)
- AWS credentials configured (`aws sts get-caller-identity`)

**Steps:**

1. **Clone core repos:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/code-generator
   git clone https://github.com/YOUR_USERNAME/runtime
   ```

2. **Build code-generator:**
   ```bash
   cd code-generator
   make build-ack-generate
   ```

3. **Clone your service controller:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/<service>-controller
   ```

4. **Verify:**
   ```bash
   ./bin/ack-generate --help
   cd <service>-controller && make test
   ```

**Common issues:**
- **Go version mismatch**: ACK requires Go 1.23+. Check `go.mod`.
- **Runtime version mismatch**: Ensure code-generator and runtime versions align.
- **Build fails**: Run `go mod tidy` and retry.

---

### 2. Adding a New Field to a CRD

**Before starting:**
- Identify the AWS API field
- Check if it's already in the CRD
- Review similar fields in the same CRD for patterns

**Steps:**

1. **Update `generator.yaml`** (only if field needs non-default behavior)

2. **Rebuild:** `SERVICE=<svc> AWS_SDK_GO_VERSION=<ver> make build-controller`

3. **Check generated code:**
   ```bash
   git diff apis/v1alpha1/
   git diff config/crd/
   ```

4. **Add custom logic** (if needed) in `pkg/resource/<resource>/hooks.go`

5. **Add tests** and test locally: `make test`

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

Some AWS APIs also wrap *input* fields in a nested structure. For example, AWS Backup's `CreateBackupPlan` requires a `BackupPlan` wrapper containing the actual plan fields.

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

---

### 3. Configuring Tags Support

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

**Special case:** Some resources have a field for tags applied to OTHER resources they create (e.g., ECR RepositoryCreationTemplate's `resourceTags` applies tags to repositories created from the template, not the template itself). The template still needs `tags.ignore: true`.

---

### 4. Implementing Cross-Resource References

**When to use:** One ACK resource needs to reference another (e.g., EC2 instance referencing a VPC).

Configure in `generator.yaml`:
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

**Common patterns:**
- **Namespace-scoped references**: Default to same namespace
- **Cross-namespace references**: Require explicit namespace in ref

---

### 5. Error Codes and Custom Hooks

**Prefer `exceptions.errors` over custom hooks for error code mapping.**

Many AWS APIs return non-standard error codes for 404 (not found). Use `exceptions.errors.404.code` in generator.yaml to map these:

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

See [ECS controller generator.yaml](https://github.com/aws-controllers-k8s/ecs-controller/blob/main/generator.yaml) for more examples. The code generator uses this to produce the correct `ackerr.NotFound` mapping in `sdkFind`.

**Custom hooks** are for cases where declarative config isn't enough (e.g., complex conditional logic, extra API calls).

1. **Create hook template:**
   `templates/hooks/<resource>/sdk_<hook_point>.go.tpl`

2. **Reference in generator.yaml:**
   ```yaml
   resources:
     BackupPlan:
       hooks:
         sdk_update_post_build_request:
           template_path: hooks/backup_plan/sdk_update_post_build_request.go.tpl
   ```

3. **Rebuild** (custom templates are picked up automatically by `make build-controller`)

**Hook template must use renamed fields:** If you renamed fields in generator.yaml, use the new names (e.g., `r.ko.Spec.Name` not `r.ko.Spec.BackupVaultName`).

**Common hook points:**
- `sdk_read_one_post_request` - After reading resource from AWS
- `sdk_create_pre_build_request` / `sdk_create_post_build_request` - Before/after building create input
- `sdk_update_pre_build_request` / `sdk_update_post_build_request` - Before/after building update input
- `sdk_delete_pre_build_request` - Before building delete input

---

### 6. Code Generation Deep Dive

**How it works:**
```
AWS API Model → ack-generate → Generated Code
     ↓              ↓              ↓
  service.json  generator.yaml  CRDs + Go types
```

**Customization patterns:**
- **Skip fields**: Add to `ignore.field_paths` in generator.yaml
- **Rename fields**: Use `renames.operations` in generator.yaml
- **Mark immutable**: Set `is_immutable: true`
- **Add validation**: Use kubebuilder markers in custom types
- **Custom conversion**: Implement in hooks

---

### 7. Contributing to the Code-Generator

**When to use:** Adding new features or fixing bugs in the code-generator itself (not a service controller).

**Code-generator test patterns:**

The code-generator has two main test categories with distinct file conventions:

1. **Model tests** (`pkg/model/model_<service>_test.go`):
   - Test CRD structure: field flattening, spec/status assignment, wrapper unwrapping
   - One file per service (e.g., `model_backup_test.go`, `model_memorydb_test.go`)
   - Verify the model layer correctly interprets generator.yaml + AWS API model

2. **Code generation tests** (`pkg/generate/code/set_sdk_test.go`):
   - Test the actual rendered Go code output
   - All services' tests go in the single `set_sdk_test.go` file
   - Call renderer functions (e.g., `code.SetSDK(...)`) and assert the generated code string
   - Verify nil checks, type conversions, and wrapper struct assignment

**When adding a new feature, add both:**
- Model test: verify the CRD is constructed correctly
- Code gen test: verify the generated Go code is correct and safe

**Test data setup:**

Each service needs test fixtures:
```
pkg/testdata/
├── codegen/sdk-codegen/aws-models/<service>.json   # AWS API model
└── models/apis/<service>/0000-00-00/generator.yaml  # Test generator config
```

**Running tests:**
```bash
make -C code-generator test
```

This runs all tests including model and code generation tests (~90 seconds).

**OriginalShapeName awareness:**

The code-generator applies "stutter removal" to shape names (e.g., `BackupBackupPlanInput` → `BackupPlanInput`) for cleaner CRD types. However, when generating code that constructs SDK types, you must use the original AWS SDK shape name.

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

**BadDefaultsAssignment map (`pkg/apiv2/remove_defaults.go`):**

The AWS SDK Go v2 has a `RemoveDefaults` customization that strips default values from Smithy shapes where the default conflicts with range constraints (e.g., a default of 0 on a field with `@range(min: 1)`). This makes those fields nillable (pointers) in the generated SDK code.

ACK mirrors this in `BadDefaultsAssignment` — a map of service name → member names that need pointer treatment. If a field is in this map but ACK doesn't treat it as a pointer, you get type errors like:

> `cannot use &f9valiter.WorkerCount (value of type **int64) as *int64 value in assignment`

**Critical gotcha:** The map keys must use Go struct member names, not Smithy shape names. These can differ (e.g., Smithy shape `WorkerCounts` → Go member `WorkerCount`). To find the correct name:
1. Check the SDK source: `codegen/sdk-codegen/aws-models/<service>.json` in [aws-sdk-go-v2](https://github.com/aws/aws-sdk-go-v2)
2. Look at the generated Go types in the SDK package to confirm the member name

**Example PR:** code-generator PR #671 (fixed `WorkerCounts` → `WorkerCount` for EMR Serverless)

**PR workflow for code-generator changes:**

1. Create feature branch from `main`
2. Add test fixtures (API model JSON + generator.yaml)
3. Add model tests and code gen tests
4. Implement the feature
5. Run `make test` to verify all tests pass
6. Squash to single commit, rebase on main before final push
7. After merge, service controllers can use the new feature by building with the new code-generator version

**Building a service controller against local code-generator changes:**
```bash
# From code-generator directory, build the service controller
SERVICE=backup make build-controller
```

---

### 8. Running Tests

**Test types:**

1. **Unit tests** (fast, no AWS):
   ```bash
   make test
   ```
   Only needed when adding custom logic in `hooks.go`, `delta.go`, etc. Generated code doesn't need unit tests.

2. **E2E tests** (real AWS, slow):
   ```bash
   cd <service>-controller
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r test/e2e/requirements.txt
   pip install setuptools  # Required for Python 3.13+
   
   export AWS_ACCOUNT_ID=123456789012
   export AWS_REGION=us-west-2
   python -m pytest test/e2e/tests/test_<resource>.py -v
   ```
   Mandatory for new controllers and resources. Use test accounts only.

**E2E tests must check the Synced condition:**
```python
from acktest.k8s import condition

time.sleep(CREATE_WAIT_AFTER_SECONDS)
assert k8s.wait_on_condition(ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)
```

**Required test coverage:** Create, Update (modify at least one field), Delete, Synced condition after each.

**E2E Test File Structure:**
```
test/e2e/
├── __init__.py              # Service constants and load helper
├── conftest.py              # pytest fixtures (boto3 client)
├── requirements.txt         # acktest dependency
├── bootstrap_resources.py   # Bootstrap resource loader
├── service_bootstrap.py     # Bootstrap lifecycle
├── service_cleanup.py       # Cleanup lifecycle
├── replacement_values.py    # Test variable defaults
├── .gitignore               # Ignore .venv, __pycache__, *.pkl
├── resources/
│   └── <resource>.yaml      # YAML fixtures with $VARIABLE placeholders
└── tests/
    ├── __init__.py
    └── test_<resource>.py   # Test classes
```

**Full test pattern with AWS verification:**
```python
from acktest.resources import random_suffix_name
from acktest.k8s import resource as k8s
from acktest.k8s import condition
import time

def test_create_delete(self, <service>_client):
    resource_name = random_suffix_name("ack-test", 24)
    replacements = REPLACEMENT_VALUES.copy()
    replacements["RESOURCE_NAME"] = resource_name
    resource_data = load_<service>_resource("resource", additional_replacements=replacements)

    ref = k8s.CustomResourceReference(CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL, resource_name, namespace="default")
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    time.sleep(CREATE_WAIT_AFTER_SECONDS)
    assert k8s.wait_on_condition(ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

    # Verify in AWS
    aws_resource = <service>_client.describe_<resource>(Name=resource_name)
    assert aws_resource is not None

    # Cleanup
    _, deleted = k8s.delete_custom_resource(ref)
    assert deleted
```

**Resource dependency cleanup:** Delete in reverse creation order.

**Common test issues:**
- **Flaky tests**: Usually timing issues, add retries or increase timeouts
- **Test pollution**: Ensure proper cleanup
- **AWS rate limits**: Add delays between operations
- **Python venv issues**: Install setuptools for Python 3.13+

---

## ACK PR Ordering for New Controllers

When building a new ACK controller or adding multiple resources, PRs should be submitted in order. Each should be merged before the next is submitted.

**PR sequence:**

1. **Bootstrap PR** - Initial controller scaffolding (code generation with all resources in `ignore.resource_names`)
   - `generator.yaml` with all resource names ignored
   - `metadata.yaml` with service info
   - Generated boilerplate: `go.mod`, `cmd/controller/main.go`, base templates
   - Helm chart skeleton, E2E test infrastructure
   - `.gitignore` (not generated — copy from another controller)
   - `README.md` updated with service name (follow existing controller format)
   - No resources yet

   **Also required for new controllers:** Add the controller to [test-infra/prow/jobs/jobs_config.yaml](https://github.com/aws-controllers-k8s/test-infra/blob/main/prow/jobs/jobs_config.yaml) so Prow can run E2E tests. Cut a separate PR to the test-infra repo.

2. **Resource PRs (one per resource)** - Each resource gets its own PR
   - Remove resource from `ignore.resource_names`
   - Add resource config to `generator.yaml`
   - Regenerate: `SERVICE=<svc> make build-controller`
   - Add E2E tests for that resource
   - Add custom hooks if needed

**Why this order:** Reviewers focus on one resource at a time, PRs are smaller, resources merge independently.

**Building against a specific code-generator version:**

For controller PRs, always build against the exact code-generator release tag, not `main`:
```bash
git -C code-generator checkout v0.57.0
SERVICE=ecr AWS_SDK_GO_VERSION=v1.41.0 make -C code-generator build-controller
```

Building from `main` (even 1 commit ahead of the tag) produces a different build hash and version string in `ack-generate-metadata.yaml`.

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

### New Resource PR Workflow Summary

1. **Edit only:** `generator.yaml`, `test/e2e/`
2. **Build:** `cd code-generator && SERVICE=<svc> AWS_SDK_GO_VERSION=<ver> make build-controller`
3. **Verify:** `git status` shows all expected generated files including Helm
4. **Test:** `source .venv/bin/activate && pytest test/e2e/tests/test_<resource>.py -v`
5. **Commit:** Single squashed commit
6. **Push:** Force push to PR branch

### Code Review Tips

- Reference related PRs for context
- Explain non-obvious choices with comments
- Include tests for new functionality
- Learn from previous review feedback — check similar merged PRs for patterns

### Common Misses

- **Helm chart not updated** - Verify with `git status` after build
- **E2E tests missing** or update test missing
- **Synced condition not checked** in E2E tests
- **SDK version not bumped** - New API fields may require newer SDK
- **Tags configuration wrong** - Not all resources support TagResource API
- **Field immutability incorrect** - Primary keys marked as mutable

---

## Troubleshooting

### Code Generation Issues

**`make build-controller` fails:**
- Check Go version (1.23+ required)
- Verify code-generator and runtime versions match
- Run `go mod tidy`
- Check generator.yaml syntax

**Field not appearing in CRD:**
- Check field isn't in `ignore.field_paths`
- Verify field exists in AWS API model
- Check for field name conflicts
- Re-run code generation

### Controller Issues

**Controller not reconciling:**
- Check CRD is installed: `kubectl get crd`
- Check controller is running: `kubectl get pods -n ack-system`
- Check RBAC: `kubectl auth can-i get <resource> --as=system:serviceaccount:ack-system:ack-<service>-controller`
- Check controller logs: `kubectl logs -n ack-system deployment/ack-<service>-controller`
- Verify AWS credentials

**Resource stuck in "Creating":**
- Check AWS API errors in logs
- Verify AWS credentials have required permissions
- Check for AWS service quotas or limits

**Field not updating:**
- Check if field is immutable in AWS API
- Verify field is in CRD spec (not status)

### Build Errors After Field Rename

**`kubectl apply` fails with "unknown field":** CRDs in cluster have old schema. Rebuild and `kubectl apply -f config/crd/bases/`.

**Controller logs "missing required field" on delete:** Delete operation not included in field renames. Add it to generator.yaml.

**Build fails with "field not found":** `zz_generated.deepcopy.go` not regenerated. Full `make build-controller` handles this automatically.

**Debugging tips:**
- Enable debug logging: `ACK_LOG_LEVEL=debug`
- Use AWS CloudTrail to see actual API calls
- Check generator config for field mapping issues

---

## Resources

### Documentation
- [ACK Documentation](https://aws-controllers-k8s.github.io/community/)
- [Contributing Guide](https://aws-controllers-k8s.github.io/community/docs/community/contributing/)
- [Developer Guide](https://aws-controllers-k8s.github.io/community/docs/contributor-docs/overview/)

### Repositories
- [Runtime](https://github.com/aws-controllers-k8s/runtime)
- [Code Generator](https://github.com/aws-controllers-k8s/code-generator)
- [Community Docs](https://github.com/aws-controllers-k8s/community)

### Community
- [GitHub Discussions](https://github.com/orgs/aws-controllers-k8s/discussions)
- [Slack Channel](https://kubernetes.slack.com/archives/C01EWFWCM9X)

### Key Team Members
- **Tech Leads**: jaypipes, a-hilaly
- **Principal Engineers**: RedbackThomson, michaelhtm
