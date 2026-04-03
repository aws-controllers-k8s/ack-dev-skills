# Troubleshooting

## Code Generation Issues

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

## Controller Issues

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

## Build Errors After Field Rename

**`kubectl apply` fails with "unknown field":** CRDs in cluster have old schema. Rebuild and `kubectl apply -f config/crd/bases/`.

**Controller logs "missing required field" on delete:** Delete operation not included in field renames. Add it to generator.yaml. Also check custom hooks — if using `input_wrapper_field_path`, fields outside the wrapper (like primary keys) won't be auto-mapped to delete input. You'll need a `sdk_delete_post_build_request` hook to set them manually.

**Build fails with "field not found":** `zz_generated.deepcopy.go` not regenerated. Full `make build-controller` handles this automatically.

## Hook Variable Names by SDK Method

Hook templates must use the correct variable name for the resource parameter. These differ by method:

| Hook point | Resource variable | Notes |
|---|---|---|
| `sdk_create_post_build_request` | `desired` | Input resource |
| `sdk_read_one_post_set_output` | `ko` | Output resource being built |
| `sdk_delete_post_build_request` | `r` | Resource to delete (NOT `latest` — that's the return var, initialized nil) |
| `sdk_update_*` | `desired`, `latest` | Desired and current state |

**Common pitfall:** Using `latest` in delete hooks causes nil pointer panic — `latest` is the return variable in `sdkDelete`, not the input.

## input_wrapper_field_path Gotchas

When using `input_wrapper_field_path`, fields that live *outside* the wrapper in the API (like `BackupPlanId` for BackupSelection) are not automatically mapped by code-gen for create, delete, or read operations. You need hooks for each:

- `sdk_create_post_build_request` — set the field on the input from `desired.ko.Spec`
- `sdk_delete_post_build_request` — set the field on the input from `r.ko.Status` (where it was stored after creation)
- `sdk_read_one_post_set_output` — copy the field from the API response into `ko.Spec` or `ko.Status`

Also: if you rename a field (e.g. `SelectionId` → `ID`), code-gen loses the mapping for delete input. Add it to the delete hook.

## E2E Test Environment Issues

**boto3 version too old for new API fields:** The test container's boto3 version is pinned by the test-infra commit in `test/e2e/requirements.txt`. If AWS API assertions fail with `KeyError` on fields that exist in the CR, update the test-infra pin to a newer commit with a current boto3.

**Express/slow-provisioning resources timeout:** Default `wait_until` timeout is 35 min. For resources that take longer (e.g. MSK Express clusters), pass `timeout_seconds=EXPRESS_WAIT_TIMEOUT_SECONDS` (60 min) only for those specific tests rather than bumping the global default.

**Kafka version compatibility:** Express brokers require specific Kafka versions. Check the `BadRequestException` error message for the valid versions list. Version format matters (e.g. `3.6.x` vs `3.6.0` vs `3.8.x`).

## Debugging Tips

- Enable debug logging: `ACK_LOG_LEVEL=debug`
- Use AWS CloudTrail to see actual API calls
- Check generator config for field mapping issues
- **Prow controller logs:** Check the `controller_logs` artifact for reconciler errors, nil panics, and API errors
- **E2E test assertions should verify both CR state AND AWS API state** (reviewer expectation)

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
