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

**Controller logs "missing required field" on delete:** Delete operation not included in field renames. Add it to generator.yaml.

**Build fails with "field not found":** `zz_generated.deepcopy.go` not regenerated. Full `make build-controller` handles this automatically.

## Debugging Tips

- Enable debug logging: `ACK_LOG_LEVEL=debug`
- Use AWS CloudTrail to see actual API calls
- Check generator config for field mapping issues

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
