# Contributing to the Code-Generator

Use this guide when adding new features or fixing bugs in the code-generator itself (not a service controller).

## Code-Generator Test Patterns

The code-generator has two main test categories with distinct file conventions:

### Model Tests (`pkg/model/model_<service>_test.go`)

- Test CRD structure: field flattening, spec/status assignment, wrapper unwrapping
- One file per service (e.g., `model_backup_test.go`, `model_memorydb_test.go`)
- Verify the model layer correctly interprets generator.yaml + AWS API model

### Code Generation Tests (`pkg/generate/code/set_sdk_test.go`)

- Test the actual rendered Go code output
- All services' tests go in the single `set_sdk_test.go` file
- Call renderer functions (e.g., `code.SetSDK(...)`) and assert the generated code string
- Verify nil checks, type conversions, and wrapper struct assignment

**When adding a new feature, add both:**
- Model test: verify the CRD is constructed correctly
- Code gen test: verify the generated Go code is correct and safe

## Test Data Setup

Each service needs test fixtures:

```
pkg/testdata/
├── codegen/sdk-codegen/aws-models/<service>.json   # AWS API model
└── models/apis/<service>/0000-00-00/generator.yaml  # Test generator config
```

## Running Tests

```bash
make -C code-generator test
```

This runs all tests including model and code generation tests (~90 seconds).

## OriginalShapeName and BadDefaultsAssignment

See [code-generation.md](code-generation.md) for details on stutter removal, `OriginalShapeName`, and the `BadDefaultsAssignment` map. These are critical when working on `varEmptyConstructorSDKType()` or adding new services to the bad defaults map.

## PR Workflow for Code-Generator Changes

1. Create feature branch from `main`
2. Add test fixtures (API model JSON + generator.yaml)
3. Add model tests and code gen tests
4. Implement the feature
5. Run `make test` to verify all tests pass
6. Squash to single commit, rebase on main before final push
7. After merge, service controllers can use the new feature by building with the new code-generator version

## Building a Service Controller Against Local Changes

```bash
# From code-generator directory, build the service controller
SERVICE=backup make build-controller
```
