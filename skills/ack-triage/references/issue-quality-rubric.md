# Issue Quality Rubric (ACK)

A bug-report issue is **actionable** when a maintainer can reproduce it (or
at least narrow root cause) without follow-up. This rubric lists what an
ACK bug report needs.

## Required for any controller bug

| Field | What it looks like | Why |
|---|---|---|
| Controller name & version | `s3-controller v1.0.6` | Behavior changes per release |
| Kubernetes version | `v1.29.0` (kind / EKS / etc.) | Some bugs are k8s-version-specific |
| Install method | Helm chart version, OLM, or manifests | Reproducer needs the same install |
| AWS region | `us-west-2` | Service availability and behavior varies |
| Reproduction steps | Numbered list with YAML manifests | Without these, nothing else helps |
| Expected behavior | One sentence | Establishes the contract |
| Actual behavior | One sentence + evidence | Establishes the gap |
| Controller logs | Kubectl command + output, or attached file | Often the fastest path to RCA |

## Strongly recommended

| Field | Why |
|---|---|
| `kubectl describe <kind> <name>` | Status conditions, events |
| Relevant CR YAML (`kubectl get <kind> <name> -o yaml`) | Reveals applied spec/status |
| AWS resource state if applicable | `aws s3api get-bucket-versioning ...` |
| `generator.yaml` excerpt for codegen issues | Custom config matters |
| Release notes / commit since last working version | Bisect hint |

## For codegen / build-time issues

| Field | Why |
|---|---|
| `code-generator` commit SHA | We rebuild from main; reproducer must match |
| `runtime` commit SHA | Same |
| `AWS_SDK_GO_VERSION` value | Field availability changes per SDK version |
| Output of `make build-controller` | The actual error path |

## For E2E / test issues

| Field | Why |
|---|---|
| Pytest invocation | What ran |
| Test name(s) failing | Where to look |
| Prow job link if applicable | Logs, artifacts |
| Flake-or-real assessment from the reporter | Steers triage |

## Classification cheat sheet

| Verdict | Meaning |
|---|---|
| **Actionable** | All required fields present; team can pick it up |
| **Needs Information** | At least one required field missing; post clarifying comment, label `triage/needs-information` |
| **Duplicate** | Same root cause as another open issue; label `triage/duplicate`, link the original, close |
| **Not Reproducible** | Tried and couldn't repro on the reported version; label `triage/not-reproducible`, ask for more detail |
| **Out of Scope** | Not an ACK bug (e.g. AWS service issue, k8s issue); explain and close |

## Anti-patterns to avoid in clarifying comments

- Don't ask for *all* missing fields if only one is critical for first-pass repro
- Don't quote the rubric verbatim — name the specific gaps
- Don't apologize; be direct and friendly
- Don't ask for redacted account IDs / ARNs that aren't needed for repro
