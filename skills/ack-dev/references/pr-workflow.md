# PR Workflow

## PR Ordering for New Controllers

When building a new ACK controller or adding multiple resources, PRs should be submitted in order. Each should be merged before the next is submitted.

### 1. Bootstrap PR

Initial controller scaffolding (code generation with all resources in `ignore.resource_names`):

- `generator.yaml` with all resource names ignored
- `metadata.yaml` with service info
- Generated boilerplate: `go.mod`, `cmd/controller/main.go`, base templates
- Helm chart skeleton, E2E test infrastructure
- `.gitignore` (not generated -- copy from another controller)
- `README.md` updated with service name (follow existing controller format)
- No resources yet

**Also required for new controllers:** Add the controller to [test-infra/prow/jobs/jobs_config.yaml](https://github.com/aws-controllers-k8s/test-infra/blob/main/prow/jobs/jobs_config.yaml) so Prow can run E2E tests. Cut a separate PR to the test-infra repo.

### 2. Resource PRs (one per resource)

Each resource gets its own PR:

- Remove resource from `ignore.resource_names`
- Add resource config to `generator.yaml`
- Regenerate: `SERVICE=<svc> make build-controller`
- Add E2E tests for that resource
- Add custom hooks if needed

**Why this order:** Reviewers focus on one resource at a time, PRs are smaller, resources merge independently.

## Building Against a Specific Code-Generator Version

For controller PRs, always build against the exact code-generator release tag, not `main`:

```bash
git -C code-generator checkout v0.57.0
SERVICE=ecr AWS_SDK_GO_VERSION=v1.41.0 make -C code-generator build-controller
```

Building from `main` (even 1 commit ahead of the tag) produces a different build hash and version string in `ack-generate-metadata.yaml`.

## Code Review Tips

- Reference related PRs for context
- Explain non-obvious choices with comments
- Include tests for new functionality
- Learn from previous review feedback -- check similar merged PRs for patterns

## Common Misses

- **Helm chart not updated** - Verify with `git status` after build
- **E2E tests missing** or update test missing
- **Synced condition not checked** in E2E tests
- **SDK version not bumped** - New API fields may require newer SDK
- **Tags configuration wrong** - Not all resources support TagResource API
- **Field immutability incorrect** - Primary keys marked as mutable
