# Running E2E Tests Locally

## Overview

ACK e2e tests run against real AWS using a local KIND (Kubernetes in Docker) cluster. The test-infra repo (`../test-infra` relative to your controller) orchestrates everything: creating the cluster, building and loading the controller image, assuming an IAM role, and running pytest.

## Prerequisites

- **docker** — builds the controller image and (optionally) the test container
- **kind** — creates the local K8s cluster
- **kubectl** — interacts with the cluster
- **yq** — parses the test config YAML
- **AWS credentials** — a configured `~/.aws/credentials` with a profile that can assume the test role
- **An IAM role** with permissions for the service under test (configured in `test_config.yaml`)

## Quick Start

```bash
cd ../test-infra

# 1. Create or update the config
# If test_config.yaml doesn't exist yet, copy the example:
cp test_config.example.yaml test_config.yaml
# If it already exists, update the relevant fields (see Configuration below)

# 2. Run the tests
make kind-test SERVICE=<service>
```

The `make kind-test` target:
1. Creates a KIND cluster (unless `cluster.create: false`)
2. Builds the controller Docker image from `../<service>-controller`
3. Loads the image into the KIND cluster
4. Installs the controller deployment with assumed-role credentials
5. Runs pytest (in a container by default, or locally if configured)

**E2E tests are long-running** (often 10–30+ minutes). When executing via Claude Code or similar tools, run the command in the background to avoid timeout issues:

```bash
# Use run_in_background: true — you'll be notified when it completes
cd ../test-infra && make kind-test SERVICE=<service>
```

Do not poll or sleep while waiting. The harness delivers a notification automatically when the process exits. Read the output at that point to check results.

## Configuration

Edit `test_config.yaml` in the test-infra root:

```yaml
cluster:
  create: true
  name: ack-<service>-test        # Optional, defaults to random
  k8s_version: 1.32.5             # Optional, defaults to latest KIND supports

aws:
  region: us-west-2
  assumed_role_arn: arn:aws:iam::<account>:role/<role-name>

tests:
  run_locally: false              # true = use local Python venv, false = container

  # Filter which tests to run (both optional):
  markers:
    # - canary
  methods:
    # - test_topic

local_build: false                # true = use go.local.mod for local runtime/codegen changes

debug:
  enabled: false
  dump_controller_logs: false     # Requires ARTIFACTS env var pointing to a log directory
```

### Key fields

| Field | Purpose |
|-------|---------|
| `cluster.create` | `true` to create a new KIND cluster, `false` to use existing kubectl context |
| `cluster.name` | Reusable cluster name — avoids recreating between runs |
| `aws.assumed_role_arn` | IAM role the controller assumes for AWS API calls |
| `tests.run_locally` | `true` runs pytest in your local venv (faster iteration), `false` builds a container |
| `tests.methods` | Filter to specific test functions (e.g., `- test_topic`) |
| `tests.markers` | Filter by pytest markers (e.g., `- canary`) |
| `local_build` | `true` uses `go.local.mod` to pick up local runtime/code-generator changes |

## Running a subset of tests

To run only the tests for a specific resource:

```yaml
tests:
  methods:
    - test_topic
```

Or by marker:

```yaml
tests:
  markers:
    - canary
```

## Running tests locally (faster iteration)

Set `tests.run_locally: true` to skip building a test container. This uses your local Python environment directly:

```yaml
tests:
  run_locally: true
```

Ensure you have the test dependencies installed in the controller's test directory:

```bash
cd ../<service>-controller/test/e2e
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install setuptools  # Required for Python 3.13+
```

## Reusing a KIND cluster between runs

Set a fixed `cluster.name` to avoid recreating the cluster each time:

```yaml
cluster:
  create: true
  name: ack-kafka-test
```

On subsequent runs, if the cluster already exists, KIND will reuse it. The controller image is rebuilt and reloaded each time.

To connect to the cluster manually:

```bash
source build/clusters/ack-<service>-test/kubecontext
kubectl get pods -n ack-system
```

## Testing with local runtime or code-generator changes

Set `local_build: true` to use `go.local.mod` which can point at local module replacements:

```yaml
local_build: true
```

This is useful when iterating on runtime or code-generator changes alongside controller changes.

## Cleaning up

```bash
# Delete all KIND clusters
make delete-all-kind-clusters

# Or delete a specific cluster
kind delete cluster --name ack-<service>-test
```

## Directory layout expectations

The test scripts expect this sibling directory structure:

```
aws-controllers-k8s/
├── test-infra/           # You run make kind-test from here
├── code-generator/       # Used to build the controller image
├── <service>-controller/ # The controller under test
│   └── test/e2e/         # Pytest tests live here
```

## Debugging test failures

When tests fail, controller logs are essential for diagnosing the root cause. Enable log dumping in `test_config.yaml`:

```yaml
debug:
  enabled: true
  dump_controller_logs: true
```

You must also set the `ARTIFACTS` environment variable to a directory where logs will be written:

```bash
export ARTIFACTS=/tmp/ack-test-logs
mkdir -p $ARTIFACTS
make kind-test SERVICE=<service>
```

After the test run completes (whether pass or fail), controller logs will be in `$ARTIFACTS/`.

If you need logs during a run (or the test hangs), connect to the cluster directly:

```bash
source build/clusters/ack-<service>-test/kubecontext
kubectl logs -n ack-system -l app.kubernetes.io/name=ack-<service>-controller --tail=200 -f
```

**Always enable `dump_controller_logs` when investigating test failures.** The pytest output alone rarely contains enough information — the controller logs show reconciliation errors, AWS API responses, and requeue reasons that explain why a resource didn't reach the expected state.

## Troubleshooting

- **"No AWS credentials found"** — Ensure `aws sts get-caller-identity` works with the profile that can assume the test role
- **KIND cluster creation fails** — Check Docker is running and has enough resources
- **Controller CrashLoopBackOff** — Check logs: `kubectl logs -n ack-system -l app.kubernetes.io/name=ack-<service>-controller`
- **Tests time out** — Some resources take a long time to provision. Increase wait timeouts in the test helper module.
- **"yq: command not found"** — Install yq v4+: `brew install yq` or `go install github.com/mikefarah/yq/v4@latest`
