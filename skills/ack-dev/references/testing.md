# Testing

## Contents
- Test Types (Unit, E2E)
- E2E Tests Must Check the Synced Condition
- E2E Test File Structure
- Full Test Pattern with AWS Verification
- E2E Tests Must Include AWS API Assertions
- test-infra Pin and boto3 Version
- Common Test Issues

## Test Types

### Unit Tests (fast, no AWS)

```bash
make test
```

Only needed when adding custom logic in `hooks.go`, `delta.go`, etc. Generated code doesn't need unit tests.

### E2E Tests (real AWS, slow)

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

## E2E Tests Must Check the Synced Condition

```python
from acktest.k8s import condition

time.sleep(CREATE_WAIT_AFTER_SECONDS)
assert k8s.wait_on_condition(ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)
```

**Required test coverage:** Create, Update (modify at least one field), Delete, Synced condition after each.

## E2E Test File Structure

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

## Full Test Pattern with AWS Verification

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

## Common Test Issues

- **Flaky tests**: Usually timing issues, add retries or increase timeouts
- **Test pollution**: Ensure proper cleanup
- **AWS rate limits**: Add delays between operations
- **Python venv issues**: Install setuptools for Python 3.13+
- **boto3 too old for new fields**: Update test-infra pin in `test/e2e/requirements.txt` to a commit with newer boto3
- **Slow-provisioning resources**: Pass explicit `timeout_seconds` to `wait_until()` for resources that take >35 min (e.g. MSK Express clusters need 60 min)
- **Static resource names**: Always use `random_suffix_name()` — static names require manual cleanup on test failure
- **No cleanup on failure**: Use pytest fixtures with `yield` so cleanup runs even when assertions fail:
  ```python
  @pytest.fixture
  def my_resource(self):
      ref, cr = create_resource(...)
      yield ref, cr
      k8s.delete_custom_resource(ref)  # Always runs
  ```
- **Missing update test**: Every resource must have create, update (modify at least one field), AND delete tests
- **CloudFormation in tests**: Don't use CF for test dependencies — use ACK resources or `acktest/bootstrapping` helpers

## E2E Tests Must Include AWS API Assertions

Reviewers expect tests to verify state via both the Kubernetes CR and direct AWS API calls. Example:

```python
# Verify via CR
cr = k8s.get_resource(ref)
assert cr["spec"]["rebalancing"]["status"] == "ACTIVE"

# Verify via AWS API
aws_resource = helper.get_by_arn(resource_arn)
assert aws_resource is not None
assert aws_resource["Rebalancing"]["Status"] == "ACTIVE"
```

Use existing helper modules (e.g. `cluster.get_by_arn()`) that wrap boto3 `describe_*` calls.

## test-infra Pin and boto3 Version

The `test/e2e/requirements.txt` pins a specific test-infra commit. That commit's `requirements.txt` determines the boto3 version in the test container. If new AWS API fields aren't visible in test assertions (KeyError), update the pin:

```
acktest @ git+https://github.com/aws-controllers-k8s/test-infra.git@<latest-commit-hash>
```
