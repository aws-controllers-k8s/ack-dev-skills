# ACK Org Repo Map

The `aws-controllers-k8s` org on GitHub is organized so that **issues live in
one place** but **PRs land in many**. Skills must understand the split.

## Where issues live

`aws-controllers-k8s/community` is the central issue tracker. Bug reports,
feature requests, and design discussions for *any* controller go there. The
repo itself contains design docs and ADRs but no controller code.

## Where PRs live

| Repo pattern | Holds | Typical PR content |
|---|---|---|
| `*-controller` | One per AWS service (e.g. `s3-controller`, `eks-controller`) | `generator.yaml` edits, custom hooks under `templates/hooks/`, E2E tests under `test/e2e/` |
| `code-generator` | `ack-generate` CLI, generator.yaml schema, build tooling | Adds/fixes the code-gen pipeline that all controllers depend on |
| `runtime` | Shared controller base library | Reconciliation framework, AWS SDK plumbing, condition handling |
| `test-infra` | Prow jobs, E2E infrastructure, onboarding | New controller onboarding, prow job config, shared E2E helpers |
| `dev-tools` | Cross-controller utilities | Scripts/tools used during release and maintenance |
| `community` | Issues, ADRs, design docs | Documentation only — no controller code |

## Common label conventions

See `references/ack-labels.md` for the canonical list. The most common
families are:

- `kind/*` — bug, feature, cleanup, documentation, test
- `area/*` — codegen, runtime, e2e, controller-name
- `priority/*` — important-soon, important-longterm, awaiting-more-evidence
- `service/*` — applied to issues that target a specific AWS service

## Implications for the maintainer skills

- **`ack-scan`** auto-discovers all repos under `aws-controllers-k8s` and
  scans both `community` (for issues) and the `*-controller`/`code-generator`/
  `runtime`/`test-infra`/`dev-tools` repos (for PRs).
- **`ack-triage`** is mostly about `community` issues, but works on any repo
  the user points it at.
- **`ack-review`** is mostly about `*-controller`, `code-generator`, and
  `runtime` PRs.
