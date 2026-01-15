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

2. **Run full code generation:**
   ```bash
   cd <service>-controller
   
   # 1. Generate API types
   ../code-generator/bin/ack-generate apis <service> \
     --generator-config-path generator.yaml \
     --metadata-config-path metadata.yaml \
     -o . \
     --refresh-cache=false \
     --template-dirs ../code-generator/templates
   
   # 2. Generate controller code
   ../code-generator/bin/ack-generate controller <service> \
     --generator-config-path generator.yaml \
     --metadata-config-path metadata.yaml \
     -o . \
     --refresh-cache=false \
     --template-dirs ../code-generator/templates \
     --template-dirs templates \
     --service-account-name ack-<service>-controller
   
   # 3. Generate deepcopy (required after API changes)
   export PATH=$PATH:$(go env GOPATH)/bin
   controller-gen object:headerFile="hack/boilerplate.go.txt" paths="./..."
   
   # 4. Generate CRDs (required for kubectl apply)
   controller-gen crd:crdVersions=v1 paths="./apis/..." output:crd:artifacts:config=config/crd/bases
   
   # 5. Fix imports
   go run golang.org/x/tools/cmd/goimports@latest -w pkg/
   ```
   
   **Why each step:**
   - `ack-generate apis` - Updates Go types in `apis/v1alpha1/`
   - `ack-generate controller` - Updates SDK integration in `pkg/resource/`
   - `controller-gen object` - Updates `zz_generated.deepcopy.go` for Kubernetes
   - `controller-gen crd` - Updates CRD YAML files for kubectl
   - `goimports` - Fixes import statements after generation

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

**Example from team PRs:**
- Adding `Tags` field: PR #1234 (s3-controller)
- Adding cross-resource reference: PR #5678 (ec2-controller)

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

### 5. Adopting Existing AWS Resources

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

### 6. Debugging Controller Issues

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

### 7. Running Tests

**When to use:** Before submitting PR, after making changes.

**Test types:**

1. **Unit tests** (fast, no AWS):
   ```bash
   make test
   ```
   
   Tests individual functions and logic.

2. **Integration tests** (mocked AWS):
   ```bash
   make test-integration
   ```
   
   Tests controller behavior with mocked AWS APIs.

3. **E2E tests** (real AWS, slow):
   ```bash
   export AWS_ACCOUNT_ID=123456789012
   export AWS_REGION=us-west-2
   make test-e2e
   ```
   
   Tests against real AWS services. **Use test accounts only.**

**Team testing patterns:**

- **Always run unit tests** before pushing
- **Run integration tests** for controller logic changes
- **Run E2E tests** for new features or AWS API changes
- **Clean up test resources** - E2E tests should delete what they create

**Writing tests:**

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

---

### 8. Custom Hooks and Templates

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

### 9. Code Generation Deep Dive

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

**Team patterns:**
- **Minimize customization**: Use generated code when possible
- **Document overrides**: Comment why custom logic is needed
- **Keep generator.yaml clean**: Only override when necessary

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
| `helm/crds/` | Copy of CRD for Helm chart |
| `helm/values.yaml` | Add to `reconcile.resources` list |
| `test/e2e/tests/test_<resource>.py` | E2E tests (create, update, delete) |
| `test/e2e/resources/<resource>.yaml` | Test resource template |

### Pre-Submit Checklist

```
[ ] Resource removed from `ignore.resource_names` in generator.yaml
[ ] All CRUD operations configured (Create, Read, Update, Delete)
[ ] Code generated: ack-generate apis + controller
[ ] CRDs generated: controller-gen crd
[ ] Deepcopy generated: controller-gen object
[ ] Code compiles: go build -o bin/controller ./cmd/controller
[ ] CRD copied to helm/crds/
[ ] Resource added to helm/values.yaml reconcile.resources
[ ] E2E tests added with create/update/delete coverage
[ ] Manual testing completed against real AWS
```

### Common Misses

- **Helm chart not updated** - CRD exists but not in `helm/crds/`, resource not in `values.yaml`
- **E2E tests missing** - Code works but no automated test coverage
- **Update test missing** - Create/delete tested but not update operations
- **SDK version not bumped** - New API fields require newer SDK version in `go.mod`

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
