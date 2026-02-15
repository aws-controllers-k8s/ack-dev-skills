---
inclusion: manual
---

# ACK Development Guide

## Overview

This guide helps you work with AWS Controllers for Kubernetes (ACK) - from setting up your development environment to implementing new features and debugging controllers. It provides step-by-step workflows based on team practices and architectural decisions from 84k+ documents including code, PRs, and Slack discussions.

## Communication Style

**Be direct and action-oriented:**

- ✅ "Added `DatabaseName` field to spec. Run `make build-controller`"
- ✅ "The field needs `is_immutable: true` in generator.yaml"
- ✅ "Check controller logs: `kubectl logs -n ack-system deployment/ack-rds-controller`"
- ❌ Don't ask "Would you like me to..." - just do it or explain what to do
- ❌ Don't explain basic concepts unless asked

**Examples:**

- **Good**: "Added field to CRD spec. Regenerate with `make build-controller`"
- **Bad**: "I can help you add a field to the CRD. First, we need to understand the generator configuration, then we'll modify the spec, and after that we'll need to regenerate..."

**When working with code:**
- Show the actual change or command
- Reference team patterns when relevant
- Link to similar PRs if helpful

**Working principles:**

1. **Do it right, not fast** - Prefer solving problems correctly over quick-and-dirty shortcuts. Take the time to implement proper solutions even if it's slower.

2. **Ask before committing** - When working interactively, always ask if the developer wants to commit or push. Never commit/push without confirmation.

3. **Use available resources** - Ask if local clones of upstream repos are available before trying to fetch remote content. Developers often have `runtime`, `code-generator`, and other ACK repos cloned locally.

---

## Common Workflows

### 1. Starting a New ACK Controller from Scratch

**When to use:** Creating a brand new ACK controller for an AWS service that doesn't have one yet.

**Prerequisites:**
- AWS service has a stable API (not in preview)
- Service is available in AWS SDK for Go v2
- You have access to the AWS service for testing
- code-generator and runtime repos cloned and built

**Steps:**

1. **Create the controller repository structure:**
   ```bash
   # Use an existing controller as a template
   git clone https://github.com/aws-controllers-k8s/s3-controller new-service-controller
   cd new-service-controller
   rm -rf .git
   git init
   ```

2. **Create minimal generator.yaml:**
   ```yaml
   ignore:
     resource_names: []  # Add resources you don't want to generate
     field_paths: []
   
   resources:
     YourResource:
       fields:
         ResourceID:
           is_primary_key: true
       tags:
         ignore: false  # or true if handling tags manually
   ```

3. **Create metadata.yaml:**
   Check AWS SDK service package name and create metadata with correct service info.

4. **Generate initial code:**
   ```bash
   # Generate APIs
   ../code-generator/bin/ack-generate apis <service> \
     --generator-config-path generator.yaml \
     --metadata-config-path metadata.yaml \
     -o . \
     --refresh-cache=false \
     --template-dirs ../code-generator/templates
   
   # Generate controller
   ../code-generator/bin/ack-generate controller <service> \
     --generator-config-path generator.yaml \
     --metadata-config-path metadata.yaml \
     -o . \
     --refresh-cache=false \
     --template-dirs ../code-generator/templates \
     --service-account-name ack-<service>-controller
   
   # Generate deepcopy
   export PATH=$PATH:$(go env GOPATH)/bin
   controller-gen object:headerFile="hack/boilerplate.go.txt" paths="./..."
   
   # Generate CRDs
   controller-gen crd:crdVersions=v1 paths="./apis/..." output:crd:artifacts:config=config/crd/bases
   ```

5. **Fix imports:**
   ```bash
   go run golang.org/x/tools/cmd/goimports@latest -w pkg/
   ```

6. **Test build:**
   ```bash
   go build -o bin/controller ./cmd/controller
   make test
   ```

**Common first-time issues:**
- **Missing controller-gen**: Install with `../code-generator/scripts/install-controller-gen.sh`
- **Import errors**: Run goimports after generation
- **CRDs not updated**: Must run controller-gen separately for CRD generation
- **Template not found**: Need both `--template-dirs ../code-generator/templates` and `--template-dirs templates` if you have custom hooks

---

### 2. Setting Up ACK Development Environment

**When to use:** First time contributing to ACK or setting up a new machine.

**Prerequisites check:**
- Go 1.23+ installed? (`go version`)
- Docker installed? (`docker --version`)
- kubectl configured? (`kubectl version`)
- AWS credentials configured? (`aws sts get-caller-identity`)

**Steps:**

1. **Fork the repositories you need:**
   ```bash
   # Core repos (most contributors need these)
   - runtime
   - code-generator
   - test-infra
   
   # Service controller (pick one you're working on)
   - s3-controller, ec2-controller, rds-controller, etc.
   ```

2. **Clone and set up code-generator:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/code-generator
   cd code-generator
   make build-ack-generate
   ```
   
   This creates `./bin/ack-generate` - the main code generation tool.

3. **Clone and set up runtime:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/runtime
   cd runtime
   make build
   ```

4. **Clone your service controller:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/s3-controller
   cd s3-controller
   make build-controller
   ```

**Verify setup:**
```bash
# In code-generator
./bin/ack-generate --help

# In service controller
make test
```

**Common issues:**
- **Go version mismatch**: ACK requires Go 1.23+. Check `go.mod` for exact version.
- **Runtime version mismatch**: Ensure code-generator and runtime versions align. Check `go.mod` in controller.
- **Build fails**: Run `go mod tidy` and retry.

---

### 3. Adding a New Field to a CRD

**Example requests:**
- "@wilder add DatabaseName field to RDS Instance CRD"
- "@wilder add Tags support to S3 Bucket"
- "@wilder make the VpcId field immutable"

**When to use:** Adding AWS API fields to an existing ACK resource.

**Before starting:**
- Identify the AWS API field you want to add
- Check if it's already in the CRD (`kubectl get crd <resource> -o yaml`)
- Review similar fields in the same CRD for patterns

**Steps:**

1. **Update the generator configuration** (if needed):
   
   Check `generator.yaml` in your service controller for field overrides or custom mappings.
   
   **Important:** Only configure fields that need non-default behavior. If a field uses all defaults (mutable, no references, etc.), don't add it to generator.yaml.

2. **Run full code generation:**
   ```bash
   cd code-generator
   export PATH=$PATH:$(go env GOPATH)/bin
   SERVICE=<service> AWS_SDK_GO_VERSION=v1.41.0 make build-controller
   ```
   
   **This single command handles everything:**
   - Generates API types in `apis/v1alpha1/`
   - Generates controller code in `pkg/resource/`
   - Generates deepcopy methods
   - Generates CRDs in `config/crd/bases/`
   - Generates RBAC manifests
   - Generates Helm chart (CRDs in `helm/crds/`, templates, values)
   - Runs gofmt and go mod tidy
   
   **Set AWS_SDK_GO_VERSION explicitly** for reproducibility. This populates `apis/v1alpha1/ack-generate-metadata.yaml`. Use the core SDK version (`github.com/aws/aws-sdk-go-v2`), not the service-specific version.
   
   **Always use make build-controller.** It takes ~30 seconds and guarantees consistency. Individual ack-generate commands can leave you with partial state (missing Helm updates, RBAC not regenerated, forgotten deepcopy/CRDs/goimports/go mod tidy).
   
   **When to run ack-generate directly (rare):**
   - Debugging whether an issue is in apis vs controller generation
   - Quick syntax check of generator.yaml changes: `ack-generate apis` to verify config parses
   - Always follow up with full `make build-controller` before testing or committing
   
   **Never manually edit generated files.** All files in `apis/v1alpha1/`, `pkg/resource/`, `config/crd/`, `config/rbac/`, and `helm/` are generated and will be overwritten.

3. **Check the generated code:**
   ```bash
   git diff apis/v1alpha1/
   git diff config/crd/
   ```
   
   Verify the field appears with correct type and validation.

4. **Add custom logic** (if needed):
   
   If the field requires special handling:
   - Add to `pkg/resource/<resource>/hooks.go`
   - Implement in `pkg/resource/<resource>/delta.go`
   
   **Team pattern**: Use hooks for custom logic, don't modify generated files.

5. **Add tests:**
   ```bash
   # Unit tests
   pkg/resource/<resource>/<resource>_test.go
   
   # Integration tests (if applicable)
   test/e2e/tests/<resource>_test.go
   ```

6. **Test locally:**
   ```bash
   make test
   make build-controller-image
   ```

**Renaming Fields for Better UX:**

AWS API field names often include redundant prefixes (e.g., `BackupVaultName`, `BackupVaultTags`). ACK allows renaming these to more idiomatic Kubernetes names.

**When to rename:**
- Field name includes the resource type (e.g., `BackupVaultName` → `Name`)
- AWS uses different tag field names (e.g., `BackupVaultTags` → `Tags`)
- Nested structures can be flattened (with limitations)

**How to rename in generator.yaml:**

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
        GetBackupVault:
          output_fields:
            BackupVaultName: Name
```

**Important:** You must add renames for ALL operations that use the field (Create, Read, Update, Delete, List).

**Result:**
```yaml
# Before
spec:
  backupVaultName: my-vault
  backupVaultTags:
    env: prod

# After
spec:
  name: my-vault
  tags:
    env: prod
```

**Limitations:**
- Can rename top-level fields easily
- Can rename one level of nesting (e.g., `BackupPlan: Plan`)
- Cannot fully flatten complex nested input types (e.g., `BackupPlanInput`)
- Simple string parameters (like S3's `Bucket`) can be flattened completely

**Testing renames:**
1. Regenerate all code (APIs, controller, deepcopy, CRDs)
2. Update any custom hook templates that reference the old field names
3. Apply updated CRDs to cluster: `kubectl apply -f config/crd/bases/`
4. Test create, update, and delete operations

**Common patterns from team:**
- **Read-only fields**: Mark with `+kubebuilder:validation:ReadOnly` in generator config
- **Required fields**: Add validation in CRD or admission webhook
- **References to other resources**: Use `AWSResourceReferenceWrapper` type
- **Sensitive data**: Store in Secrets, reference from spec
- **Immutable fields**: Check AWS API docs carefully - a field being "required" in Update doesn't mean it's mutable. Primary keys and lookup identifiers are almost always immutable.
- **Nested API responses**: If AWS API wraps the response (e.g., `{ "resource": { ...fields... } }`), add `output_wrapper_field_path` to operations in generator.yaml to avoid bloated status fields.

**Field Immutability - How to Verify:**

A field should be marked `is_immutable: true` if:
1. AWS API docs say "cannot be changed" or "immutable"
2. The field is a primary key or lookup identifier (even if required in Update)
3. Testing with AWS CLI shows the field cannot be updated

**Example:**
```yaml
resources:
  RepositoryCreationTemplate:
    fields:
      Prefix:
        is_primary_key: true
        is_immutable: true  # Prefix identifies WHICH template, can't change it
```

**Nested Response Handling:**

Some AWS APIs wrap responses in a nested object. Without configuration, the entire wrapper ends up in Status.

**Check the AWS API response shape:**
```bash
aws <service> <operation> help
# Look for response structure like:
# {
#   "resourceName": {
#     "field1": "value",
#     ...
#   }
# }
```

**Configure in generator.yaml:**
```yaml
operations:
  CreateResource:
    output_wrapper_field_path: ResourceName
  UpdateResource:
    output_wrapper_field_path: ResourceName
  DescribeResources:
    output_wrapper_field_path: ResourceNames  # Note: plural for list operations
```

**Example from team PRs:**
- Adding `Tags` field: PR #1234 (s3-controller)
- Adding cross-resource reference: PR #5678 (ec2-controller)
- ECR RepositoryCreationTemplate with output_wrapper_field_path: PR #142 (ecr-controller)

**Nested Input Handling (`input_wrapper_field_path`):**

Some AWS APIs also wrap *input* fields in a nested structure. For example, AWS Backup's `CreateBackupPlan` requires a `BackupPlan` wrapper containing the actual plan fields (`BackupPlanName`, `Rules`, etc.).

Without configuration, users would need to nest fields under `spec.backupPlan.backupPlanName`. With `input_wrapper_field_path`, the wrapper's fields are flattened directly into the CRD Spec.

**Configure in generator.yaml:**
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

**Result:**
```yaml
# Without input_wrapper_field_path (nested)
spec:
  backupPlan:
    backupPlanName: my-plan
    rules: [...]

# With input_wrapper_field_path (flattened)
spec:
  name: my-plan
  rules: [...]
```

**How it works internally:**
- During CRD construction (`model.go`), the wrapper's member fields are added to Spec instead of the wrapper itself. Fields outside the wrapper are excluded (consistent with `output_wrapper_field_path` behavior).
- During code generation (`set_sdk.go`), a wrapper struct variable (`fw`) is created, populated from Spec fields, then assigned to the input shape's wrapper field (e.g., `res.BackupPlan = fw`).
- The `getWrapperShape` function in `crd.go` handles both input and output unwrapping, including list-of-structure wrappers.

**Current limitations:**
- Only structure wrappers are supported at the top level in `model.go` during CRD construction
- Nested paths (e.g., `a.b.c` where `b` is a list) could be extended in a future PR
- The code-generation side (`crd.go`) already handles list types via `getWrapperShape`

**Example from team PRs:**
- Backup BackupPlan with input_wrapper_field_path: PR #657 (code-generator)

---

### 4. Implementing Cross-Resource References

**Example requests:**
- "@wilder add VPC reference to EC2 Instance"
- "@wilder implement SecurityGroup reference for RDS"
- "@wilder fix the subnet reference resolution"

**When to use:** One ACK resource needs to reference another (e.g., EC2 instance referencing a VPC).

**Team pattern:** Use `AWSResourceReferenceWrapper` for all cross-resource references.

**Steps:**

1. **Define the reference field in CRD spec:**
   ```go
   // In generator config or custom types
   VPCRef *ackv1alpha1.AWSResourceReferenceWrapper `json:"vpcRef,omitempty"`
   ```

2. **Implement resolution logic:**
   
   In `pkg/resource/<resource>/references.go`:
   ```go
   func (rm *resourceManager) ResolveReferences(
       ctx context.Context,
       r *resource,
   ) (*resource, error) {
       if r.ko.Spec.VPCRef != nil {
           vpcID, err := rm.resolveVPCReference(ctx, r.ko.Spec.VPCRef)
           if err != nil {
               return nil, err
           }
           r.ko.Spec.VPCID = &vpcID
       }
       return r, nil
   }
   ```

3. **Handle reference not found:**
   
   **Team decision** (from tech lead a-hilaly): Return error, don't create resource with invalid reference.
   
   ```go
   if vpcID == "" {
       return nil, ackerr.NewTerminalError(
           fmt.Errorf("referenced VPC not found"),
       )
   }
   ```

4. **Add tests:**
   - Test valid reference resolution
   - Test reference not found error
   - Test reference to non-existent resource

**Common patterns:**
- **Namespace-scoped references**: Default to same namespace
- **Cross-namespace references**: Require explicit namespace in ref
- **Circular references**: Detect and reject during validation

**Example PRs:**
- VPC reference in EC2: PR #2345
- Security group references: PR #3456

---

### 5. Configuring Tags Support

**When to use:** Adding or configuring tag support for a resource.

**Important:** Not all resources support tagging via the TagResource API. Check AWS documentation first.

**How to check if TagResource is supported:**

```bash
aws <service> tag-resource help
# Look for: "Currently, the only supported resource is..." or similar language
```

**Example - ECR:**
- `Repository` - supports TagResource ✓
- `RepositoryCreationTemplate` - does NOT support TagResource ✗
- `PullThroughCacheRule` - does NOT support TagResource ✗

**For resources that support TagResource:**

```yaml
resources:
  Repository:
    tags:
      ignore: false  # Default, enables tag support
```

**For resources that do NOT support TagResource:**

```yaml
resources:
  RepositoryCreationTemplate:
    tags:
      ignore: true  # Disables tag support
```

**Special case - Tags on created resources:**

Some resources have a field for tags that get applied to OTHER resources they create, not tags on the resource itself.

**Example - ECR RepositoryCreationTemplate:**
- Has `resourceTags` field
- These tags are applied to repositories created FROM the template
- The template itself cannot be tagged
- Configuration: `tags.ignore: true`

**Testing tag support:**

1. Create resource with tags in spec
2. Verify tags appear in AWS Console or CLI
3. Update tags in spec
4. Verify tags update in AWS
5. Delete resource
6. Verify tags are removed with resource

---

### 6. Adopting Existing AWS Resources

**When to use:** User wants ACK to manage an existing AWS resource (not created by ACK).

**Team pattern:** Use adoption annotations, don't auto-adopt without explicit user intent.

**Steps:**

1. **User adds adoption annotation:**
   ```yaml
   apiVersion: s3.services.k8s.aws/v1alpha1
   kind: Bucket
   metadata:
     name: my-bucket
     annotations:
       services.k8s.aws/adoption-policy: "adopt"
   spec:
     name: existing-bucket-name
   ```

2. **Controller discovers existing resource:**
   
   In `pkg/resource/<resource>/hooks.go`:
   ```go
   func (rm *resourceManager) sdkFind(
       ctx context.Context,
       r *resource,
   ) (*resource, error) {
       // Check if resource exists in AWS
       resp, err := rm.sdkapi.DescribeBucket(...)
       if err != nil {
           if awsErr, ok := ackerr.AWSError(err); ok {
               if awsErr.Code() == "NoSuchBucket" {
                   return nil, ackerr.NotFound
               }
           }
           return nil, err
       }
       
       // Merge AWS state with desired state
       return rm.setResourceFromDescribe(r, resp), nil
   }
   ```

3. **Merge existing state with desired state:**
   
   **Team decision**: Preserve AWS state, only update fields specified in spec.
   
   ```go
   // Don't overwrite fields not in spec
   if r.ko.Spec.Field == nil {
       r.ko.Spec.Field = aws.String(existingValue)
   }
   ```

4. **Handle adoption conflicts:**
   - Tags mismatch: Merge tags, prefer spec
   - Configuration drift: Update to match spec
   - Immutable fields: Reject if different

**Common patterns:**
- **Adoption with validation**: Check resource is in expected state
- **Partial adoption**: Only adopt if certain conditions met
- **Adoption rollback**: Support un-adopting (removing from ACK management)

**Example PRs:**
- S3 bucket adoption: PR #4567
- RDS instance adoption: PR #5678

---

### 7. Debugging Controller Issues

**Example requests:**
- "@wilder debug why my S3 bucket is stuck in Creating"
- "@wilder check the RDS controller logs for errors"
- "@wilder why isn't the controller reconciling this resource"

**When to use:** Controller not reconciling, resources stuck, or unexpected behavior.

**Quick diagnostics:**

1. **Check controller logs:**
   ```bash
   kubectl logs -n ack-system deployment/ack-<service>-controller
   ```
   
   Look for:
   - `ERROR` or `WARN` messages
   - AWS API errors
   - Reconciliation failures

2. **Check resource status:**
   ```bash
   kubectl describe <resource-type> <resource-name>
   ```
   
   Look for:
   - `Status.Conditions` - error messages
   - `Status.ACKResourceMetadata` - AWS resource info
   - Events - recent reconciliation attempts

3. **Check RBAC permissions:**
   ```bash
   kubectl auth can-i get <resource> --as=system:serviceaccount:ack-system:ack-<service>-controller
   ```

4. **Verify AWS credentials:**
   ```bash
   # Check controller has valid credentials
   kubectl get secret -n ack-system ack-<service>-user-secrets
   ```

**Common issues:**

**Controller not reconciling:**
- Check CRD is installed: `kubectl get crd`
- Check controller is running: `kubectl get pods -n ack-system`
- Check controller logs for startup errors

**Resource stuck in "Creating":**
- Check AWS API errors in logs
- Verify AWS credentials have required permissions
- Check for AWS service quotas or limits

**Field not updating:**
- Check if field is immutable in AWS API
- Verify field is in CRD spec (not status)
- Check for field validation errors

**AWS resource exists but ACK doesn't see it:**
- Check resource name/ID matches
- Verify AWS region matches controller config
- Check for adoption annotations if needed

**Team debugging patterns:**
- **Enable debug logging**: Set `ACK_LOG_LEVEL=debug`
- **Use AWS CloudTrail**: See actual API calls made
- **Check generator config**: Verify field mappings are correct

---

### 8. Running Tests

**When to use:** Before submitting PR, after making changes.

**Test types:**

1. **Unit tests** (fast, no AWS):
   ```bash
   make test
   ```
   
   Tests individual functions and logic.
   Only needed when adding custom logic in `hooks.go`, `delta.go`, etc.
   Generated code does not need unit tests - E2E tests provide coverage.

2. **Integration tests** (mocked AWS):
   ```bash
   make test-integration
   ```
   
   Tests controller behavior with mocked AWS APIs.

3. **E2E tests** (real AWS, slow):
   ```bash
   # Setup Python environment (first time only)
   cd <service>-controller
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r test/e2e/requirements.txt
   pip install setuptools  # Required for Python 3.13+ (distutils removed)
   
   # Run tests
   source .venv/bin/activate
   export AWS_ACCOUNT_ID=123456789012
   export AWS_REGION=us-west-2
   python -m pytest test/e2e/tests/test_<resource>.py -v
   ```
   
   Tests against real AWS services. **Use test accounts only.**
   These are mandatory for new controllers and resources.
   
   **Note:** Each bash command runs in a fresh shell, so you need to source the venv each time when running via automation.

**Team testing patterns:**

- **Always run unit tests** before pushing
- **Run integration tests** for controller logic changes
- **Run E2E tests** for new features or AWS API changes
- **Clean up test resources** - E2E tests should delete what they create

**Writing E2E tests:**

E2E tests **must check the Synced condition** to verify the K8s resource reaches a synced state:

```python
from acktest.k8s import condition
import time

# After create
time.sleep(CREATE_WAIT_AFTER_SECONDS)
assert k8s.wait_on_condition(ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

# After update
time.sleep(UPDATE_WAIT_AFTER_SECONDS)
assert k8s.wait_on_condition(ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)
```

**Required test coverage:**
- Create operation
- Update operation (modify at least one field)
- Delete operation
- Synced condition verification after each operation

**Writing unit tests:**

Follow existing test patterns in the codebase:
```go
// Unit test example
func TestResourceManager_sdkFind(t *testing.T) {
    // Setup
    rm := &resourceManager{...}
    
    // Test
    result, err := rm.sdkFind(ctx, resource)
    
    // Assert
    assert.NoError(t, err)
    assert.Equal(t, expected, result)
}
```

**Common test issues:**
- **Flaky tests**: Usually timing issues, add retries or increase timeouts
- **Test pollution**: Tests affecting each other, ensure proper cleanup
- **AWS rate limits**: E2E tests hitting API limits, add delays or use mocks
- **Python venv issues**: Make sure setuptools is installed for Python 3.13+

**E2E Test File Structure:**

When creating E2E tests for a new controller or resource:

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

**Key file templates:**

`test/e2e/__init__.py`:
```python
import pytest
from pathlib import Path
from acktest.resources import load_resource_file

SERVICE_NAME = "<service>"
CRD_GROUP = "<service>.services.k8s.aws"
CRD_VERSION = "v1alpha1"

service_marker = pytest.mark.service(arg=SERVICE_NAME)
bootstrap_directory = Path(__file__).parent
resource_directory = Path(__file__).parent / "resources"

def load_<service>_resource(resource_name: str, additional_replacements: dict = {}):
    return load_resource_file(resource_directory, resource_name, additional_replacements=additional_replacements)
```

`test/e2e/conftest.py`:
```python
import boto3
import pytest

@pytest.fixture(scope="module")
def <service>_client():
    return boto3.client("<service>")
```

`test/e2e/requirements.txt`:
```
acktest @ git+https://github.com/aws-controllers-k8s/test-infra.git@<commit-hash>
```

**YAML fixture pattern** (`test/e2e/resources/<resource>.yaml`):
```yaml
apiVersion: <service>.services.k8s.aws/v1alpha1
kind: <Resource>
metadata:
  name: $RESOURCE_NAME
spec:
  name: $RESOURCE_NAME
  # other fields...
```

**Test pattern with AWS verification:**
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
    
    # Verify in AWS using boto3
    aws_resource = <service>_client.describe_<resource>(Name=resource_name)
    assert aws_resource is not None
    
    # Cleanup
    _, deleted = k8s.delete_custom_resource(ref)
    assert deleted
```

**Resource dependency cleanup order:**

When testing resources with dependencies (e.g., BackupPlan depends on BackupVault), delete in reverse order:
```python
# Create: vault first, then plan
# Delete: plan first, then vault
_, deleted = k8s.delete_custom_resource(plan_ref)
time.sleep(DELETE_WAIT_AFTER_SECONDS)
_, deleted = k8s.delete_custom_resource(vault_ref)
```

---

### 9. Custom Hooks and Templates

**When to use:** AWS API behavior requires custom logic that generated code can't handle.

**Example scenario:** AWS Backup's DescribeBackupVault returns `AccessDeniedException` (403) instead of `ResourceNotFoundException` (404) when a vault doesn't exist. This makes it impossible to distinguish between "vault doesn't exist" and "no permission to describe vault".

**Solution: Custom hook template**

1. **Create hook template directory:**
   ```bash
   mkdir -p templates/hooks/backup_vault
   ```

2. **Add template file:**
   
   `templates/hooks/backup_vault/sdk_read_one_post_request.go.tpl`
   
   ```go
   if err != nil {
       var awsErr smithy.APIError
       if errors.As(err, &awsErr) {
           if awsErr.ErrorCode() == "AccessDeniedException" {
               // Custom logic to check if resource exists
               // Return ackerr.NotFound if it doesn't exist
           }
       }
   }
   ```

3. **Reference in generator.yaml:**
   ```yaml
   resources:
     BackupVault:
       hooks:
         sdk_read_one_post_request:
           template_path: hooks/backup_vault/sdk_read_one_post_request.go.tpl
   ```

4. **Regenerate with custom templates:**
   ```bash
   ../code-generator/bin/ack-generate controller <service> \
     --template-dirs ../code-generator/templates \
     --template-dirs templates \
     ...
   ```

**Important:** When regenerating, you must include BOTH template directories:
- `../code-generator/templates` (base templates)
- `templates` (your custom templates)

**Hook template must use renamed fields:** If you renamed fields in generator.yaml, update the hook template to use the new names (e.g., `r.ko.Spec.Name` not `r.ko.Spec.BackupVaultName`).

**Common hook types:**
- `sdk_read_one_post_request` - After reading resource from AWS
- `sdk_create_pre_build_request` - Before creating resource
- `sdk_update_pre_build_request` - Before updating resource
- `sdk_delete_pre_build_request` - Before deleting resource

---

### 10. Code Generation Deep Dive

**When to use:** Understanding how code generation works, customizing generation.

**How it works:**

```
AWS API Model → ack-generate → Generated Code
     ↓              ↓              ↓
  service.json  generator.yaml  CRDs + Go types
```

**Key files:**

1. **`generator.yaml`** - Configuration for code generation:
   ```yaml
   ignore:
     resource_names:
       - InternalResource  # Don't generate CRD
     field_paths:
       - CreateInput.InternalField  # Skip this field
   
   resources:
     Bucket:
       fields:
         Name:
           is_immutable: true
           is_required: true
   ```

2. **`apis/v1alpha1/types.go`** - Custom types (not generated):
   ```go
   // Add custom types here
   type CustomConfig struct {
       Field string `json:"field"`
   }
   ```

3. **`pkg/resource/<resource>/hooks.go`** - Custom logic:
   ```go
   // Override generated behavior
   func (rm *resourceManager) customSetOutput(...) {
       // Custom logic here
   }
   ```

**Customization patterns:**

- **Skip fields**: Add to `ignore.field_paths` in generator.yaml
- **Rename fields**: Use `fields.<Field>.name` in generator.yaml
- **Mark immutable**: Set `is_immutable: true`
- **Add validation**: Use kubebuilder markers in custom types
- **Custom conversion**: Implement in hooks.go

**What files to edit vs. never edit:**

**Edit these:**
- `generator.yaml` - All resource configuration
- `templates/hooks/` - Custom hook templates (if needed)
- `test/e2e/` - E2E tests

**Never edit these (generated and will be overwritten):**
- `apis/v1alpha1/*.go` - Generated API types
- `pkg/resource/<resource>/*.go` - Generated SDK code
- `config/crd/bases/*.yaml` - Generated CRDs
- `config/rbac/*.yaml` - Generated RBAC
- `helm/crds/*.yaml` - Generated Helm CRDs
- `helm/templates/*.yaml` - Generated Helm templates
- `cmd/controller/main.go` - Generated controller entrypoint

**If you see formatting issues or incorrect code in generated files:** Fix the generator.yaml configuration and regenerate. Don't manually edit.

**Team patterns:**
- **Minimize customization**: Use generated code when possible
- **Document overrides**: Comment why custom logic is needed
- **Keep generator.yaml clean**: Only override when necessary - if a field uses all defaults, don't add it to generator.yaml

---

### 11. Contributing to the Code-Generator

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
- Code gen test: verify the generated Go code is correct and safe (nil checks, type references)

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
// Correct: uses original SDK name
if shape.Type == "structure" && shape.OriginalShapeName != "" {
    goType = "svcsdktypes." + shape.OriginalShapeName
}
```

Without this, generated code would reference non-existent SDK types when stutter removal has renamed them.

**PR workflow for code-generator changes:**

1. Create feature branch from `main`
2. Add test fixtures (API model JSON + generator.yaml)
3. Add model tests and code gen tests
4. Implement the feature
5. Run `make test` to verify all tests pass
6. Squash to single commit, rebase on main before final push
7. After merge, service controllers can use the new feature by building with the new code-generator version

**Building a service controller against local code-generator changes:**

When testing code-generator changes against a real controller:
```bash
# From code-generator directory, build the service controller
SERVICE=backup make build-controller
```

This uses your local code-generator code to generate the controller, so you can verify end-to-end behavior before merging.

---

## ACK PR Ordering for New Controllers

When building a new ACK controller or adding multiple resources, PRs should be submitted in a specific order. Each PR builds on the previous one and should be merged before the next is submitted.

**PR sequence:**

1. **Bootstrap PR** - Initial controller scaffolding
   - `generator.yaml` with resource names in `ignore.resource_names` (all ignored initially)
   - Generated boilerplate: `go.mod`, `cmd/controller/main.go`, base templates
   - Helm chart skeleton
   - No resources yet - just the empty controller

2. **Controller implementation PR** - Core controller setup
   - Any shared custom hooks or utilities
   - E2E test infrastructure (`test/e2e/__init__.py`, `conftest.py`, etc.)
   - RBAC and service-level configuration

3. **Resource PRs (one per resource)** - Each resource gets its own PR
   - Remove resource from `ignore.resource_names`
   - Add resource config to `generator.yaml` (fields, renames, hooks, tags)
   - Regenerate: `SERVICE=<svc> make build-controller`
   - Add E2E tests for that resource
   - Each PR is self-contained and reviewable independently

**Why this order matters:**
- Reviewers can focus on one resource at a time
- Each PR is smaller and easier to review
- Resources can be merged incrementally as they pass review
- If one resource has issues, it doesn't block others

**Example from team:**
- ECR controller: Bootstrap → Controller impl → Repository (existing) → PullThroughCacheRule → RepositoryCreationTemplate (PR #142)

**Building against a specific code-generator version:**

For controller PRs, always build against the exact code-generator release tag, not `main`:
```bash
git -C code-generator checkout v0.57.0
SERVICE=ecr AWS_SDK_GO_VERSION=v1.41.0 make -C code-generator build-controller
```

This ensures `ack-generate-metadata.yaml` shows the correct version and build hash. Building from `main` (even if it's only 1 commit ahead of the tag) will produce a different build hash and version string.

---

## PR Checklist for New Resources

When adding a new resource to an existing ACK controller, ensure the PR includes ALL of the following:

### Required Files

| File/Location | Purpose |
|---------------|---------|
| `generator.yaml` | Resource config (remove from ignore, add fields/renames/hooks) |
| `apis/v1alpha1/` | Generated API types |
| `pkg/resource/<resource>/` | Generated controller code |
| `config/crd/bases/` | Generated CRD definitions |
| `helm/crds/` | Copy of CRD for Helm chart (auto-generated by make build-controller) |
| `helm/values.yaml` | Add to `reconcile.resources` list (auto-generated by make build-controller) |
| `test/e2e/tests/test_<resource>.py` | E2E tests (create, update, delete) |
| `test/e2e/resources/<resource>.yaml` | Test resource template |

### Pre-Submit Checklist

```
[ ] Resource removed from `ignore.resource_names` in generator.yaml
[ ] All CRUD operations configured (Create, Read, Update, Delete)
[ ] Code generated from code-generator directory: SERVICE=<svc> AWS_SDK_GO_VERSION=<ver> make build-controller
[ ] Verify git status shows all expected generated files including Helm
[ ] Code compiles: go build -o bin/controller ./cmd/controller
[ ] Unit tests added for any custom logic and hooks
[ ] E2E tests added with create/update/delete coverage
[ ] E2E tests verify Synced condition after operations
[ ] Manual testing completed against real AWS resources
[ ] Commits squashed into single commit with attribution
```

### New Resource PR Workflow Summary

1. **Edit only:** `generator.yaml`, `test/e2e/`
2. **Build:** `cd code-generator && SERVICE=<svc> AWS_SDK_GO_VERSION=<ver> make build-controller`
3. **Verify:** `git status` shows all expected generated files including Helm
4. **Test:** `source .venv/bin/activate && pytest test/e2e/tests/test_<resource>.py -v`
5. **Commit:** Single squashed commit with attribution
6. **Push:** Force push to PR branch

**Never manually edit generated files. If something's wrong, fix generator.yaml and rebuild.**

### Common Misses

- **Helm chart not updated** - Should be automatic with make build-controller, verify with git status
- **E2E tests missing** - Code works but no automated test coverage
- **Update test missing** - Create/delete tested but not update operations
- **Synced condition not checked** - E2E tests don't verify resource reaches synced state
- **SDK version not bumped** - New API fields require newer SDK version in `go.mod`
- **Tags configuration wrong** - Not all resources support TagResource API, check AWS docs
- **Field immutability incorrect** - Primary keys marked as mutable, or mutable fields marked immutable
- **Manual edits to generated files** - Will be overwritten on next generation

---

## Best Practices

### Development

- **Use latest runtime version** - Ensures compatibility and bug fixes
- **Follow Go conventions** - Standard project layout and naming
- **Don't modify generated code** - Use hooks and custom types
- **Keep PRs focused** - One feature or fix per PR

### Code Reviews

- **Reference related PRs** - Link to similar changes
- **Explain non-obvious choices** - Add comments for complex logic
- **Include tests** - Cover new functionality
- **Follow team feedback** - Learn from previous reviews

### Commit Hygiene

**Squash commits before final push:**

```bash
git reset --soft <base-commit>
git commit -m "add support for <Resource> resource

thanks to @original-author for initial PR"
git push --force origin <branch>
```

**Why:** Clean history, single commit per feature, easier to review and revert.

**Best practices:**
- One commit per feature or resource
- Include attribution for co-authors or original work
- Use descriptive commit messages
- Force push to PR branch after squashing

### Team Patterns

- **Tech lead decisions** - Reference jaypipes, a-hilaly for architecture
- **Principal engineer patterns** - Follow RedbackThomson, michaelhtm for implementation
- **Community discussions** - Check Slack and GitHub Discussions for context

---

## Troubleshooting

### Code Generation Issues

**Problem**: `make build-controller` fails

**Solutions**:
- Check Go version (1.23+ required)
- Verify code-generator and runtime versions match
- Run `go mod tidy`
- Check generator.yaml syntax

**Problem**: Field not appearing in CRD

**Solutions**:
- Check field isn't in `ignore.field_paths`
- Verify field exists in AWS API model
- Check for field name conflicts
- Re-run code generation

### Controller Issues

**Problem**: Controller not reconciling

**Solutions**:
- Check RBAC permissions
- Verify AWS credentials
- Check controller logs
- Ensure CRD is installed

**Problem**: AWS API errors

**Solutions**:
- Check AWS credentials have required permissions
- Verify AWS service quotas
- Check for AWS service issues
- Review CloudTrail logs

### CRD Field Validation Errors

**Problem:** `kubectl apply` fails with "unknown field spec.name"

**Cause:** CRDs in cluster have old schema, but you're using new field names.

**Solution:**
```bash
# Regenerate CRDs
controller-gen crd:crdVersions=v1 paths="./apis/..." output:crd:artifacts:config=config/crd/bases

# Apply updated CRDs
kubectl apply -f config/crd/bases/
```

### Delete Operation Fails

**Problem:** Controller logs show "missing required field" on delete

**Cause:** Delete operation not included in field renames.

**Solution:** Add delete operation to renames in generator.yaml:
```yaml
renames:
  operations:
    DeleteBackupVault:
      input_fields:
        BackupVaultName: Name
```

### Deepcopy Errors After Field Rename

**Problem:** Build fails with "field BackupVaultName not found"

**Cause:** `zz_generated.deepcopy.go` not regenerated after field rename.

**Solution:**
```bash
controller-gen object:headerFile="hack/boilerplate.go.txt" paths="./..."
```

### Test Issues

**Problem**: Tests failing

**Solutions**:
- Check test dependencies
- Verify mock setup
- Check for race conditions
- Review test logs
- Ensure proper cleanup

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
- [Weekly Meetings](https://aws-controllers-k8s.github.io/community/docs/community/meetings/)

### Key Team Members
- **Tech Leads**: jaypipes, a-hilaly
- **Principal Engineers**: RedbackThomson, michaelhtm
- Check GitHub for current team roster
